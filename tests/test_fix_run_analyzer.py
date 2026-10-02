#!/usr/bin/env python3
"""run_analyzer 冒烟级离线测试。

真实 `dart analyze` 需要 Flutter/Dart SDK（记入 tests/SKIPPED.md）；
此处用 mock subprocess 覆盖解析/分类/退出码逻辑，另用真实 FileNotFoundError
路径验证 dart 未安装时的显性报错。
"""
import io
import json
import os
import sys
import unittest
from contextlib import redirect_stdout
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from scripts.fix import run_analyzer as ra
from scripts.fix.run_analyzer import ANALYZER_FIX_DOC, main, route_error_code, run_analyzer


def _fake_result(returncode=0, stdout="", stderr=""):
    result = mock.Mock()
    result.returncode = returncode
    result.stdout = stdout
    result.stderr = stderr
    return result


def _diag(severity, code, message, file, line, column):
    """dart analyze --format=json 的真实 diagnostic 形态（severity 大写、
    消息在 problemMessage、位置在 location.range.start，0-based）。"""
    return {
        "code": code,
        "severity": severity,
        "type": "COMPILE_TIME_ERROR" if severity == "ERROR" else "WARNING",
        "location": {
            "file": file,
            "range": {"start": {"offset": 0, "line": line, "column": column}},
        },
        "problemMessage": message,
    }


def _diagnostics_payload():
    return json.dumps(
        {
            "diagnostics": [
                _diag("WARNING", "unused_import", "Unused import.",
                      "lib/b.dart", 3, 8),
                _diag("ERROR", "use_build_context_synchronously",
                      "Don't use BuildContext across async gaps.",
                      "lib/a.dart", 10, 3),
                _diag("INFO", "prefer_single_quotes", "Prefer single quotes.",
                      "lib/c.dart", 1, 1),
            ]
        }
    )


class TestRouteErrorCode(unittest.TestCase):
    def test_known_code(self):
        routed = route_error_code("unused_import")
        self.assertEqual(routed["doc"], ANALYZER_FIX_DOC)
        self.assertIn("import", routed["hint"])

    def test_unknown_code_empty_hint(self):
        routed = route_error_code("totally_unknown_code_xyz")
        self.assertEqual(routed["hint"], "")
        self.assertEqual(routed["code"], "totally_unknown_code_xyz")


class TestRunAnalyzer(unittest.TestCase):
    def test_classify_and_sort(self):
        with mock.patch.object(
            ra.subprocess, "run", return_value=_fake_result(0, _diagnostics_payload())
        ):
            result = run_analyzer("/tmp/proj")
        self.assertIsNone(result["error"])
        self.assertEqual(result["total"], 3)
        self.assertEqual(len(result["errors"]), 1)
        self.assertEqual(len(result["warnings"]), 1)
        self.assertEqual(len(result["infos"]), 1)
        self.assertEqual(result["errors"][0]["code"], "use_build_context_synchronously")
        self.assertTrue(result["errors"][0]["hint"])
        self.assertEqual(result["warnings"][0]["code"], "unused_import")
        # 真实 dart 字段提取（大写 severity 归一 + problemMessage + location）
        err = result["errors"][0]
        self.assertEqual(err["severity"], "error")
        self.assertIn("BuildContext", err["error_message"])
        self.assertEqual(err["file"], "lib/a.dart")
        self.assertEqual(err["line"], 10)
        self.assertEqual(err["column"], 3)

    def test_real_dart_invalid_assignment_regression(self):
        # 2026-10-02 真机实测抓到的回归：真实 dart 输出 severity 为大写，
        # 旧实现按小写分桶导致 total=1 但 errors=[] 的静默失真。
        real = json.dumps({
            "diagnostics": [{
                "code": "invalid_assignment",
                "severity": "ERROR",
                "type": "COMPILE_TIME_ERROR",
                "location": {
                    "file": "/tmp/flutter_e2e/lib/main.dart",
                    "range": {"start": {"offset": 4825, "line": 124, "column": 20}},
                },
                "problemMessage": "A value of type 'String' can't be assigned to a variable of type 'int'.",
            }]
        })
        with mock.patch.object(
            ra.subprocess, "run", return_value=_fake_result(1, real)
        ):
            result = run_analyzer("/tmp/flutter_e2e")
        self.assertEqual(result["total"], 1)
        self.assertEqual(len(result["errors"]), 1)
        self.assertEqual(result["errors"][0]["code"], "invalid_assignment")
        self.assertIn("can't be assigned", result["errors"][0]["error_message"])

    def test_stdout_prefix_fallback(self):
        noisy = "Analyzing myapp...\n" + _diagnostics_payload()
        with mock.patch.object(ra.subprocess, "run", return_value=_fake_result(0, noisy)):
            result = run_analyzer(".")
        self.assertIsNone(result["error"])
        self.assertEqual(result["total"], 3)

    def test_issue_exit_code_with_json_is_ok(self):
        # dart analyze 发现 error 时退出码非零但仍输出有效 JSON（非工具失败）
        with mock.patch.object(
            ra.subprocess, "run", return_value=_fake_result(1, _diagnostics_payload())
        ):
            result = run_analyzer(".")
        self.assertIsNone(result["error"])
        self.assertEqual(result["total"], 3)

    def test_dart_not_found_real_fileerror(self):
        result = run_analyzer(".", dart_bin="/nonexistent/dart-binary-xyz")
        self.assertIn("dart 可执行文件未找到", result["error"])

    def test_tool_failure_exit_code(self):
        with mock.patch.object(
            ra.subprocess, "run", return_value=_fake_result(69, "fatal:", "sdk missing")
        ):
            result = run_analyzer(".")
        self.assertIn("dart analyze 失败 (exit=69)", result["error"])
        self.assertEqual(result["total"], 0)

    def test_issue_exit_code_but_bad_json(self):
        with mock.patch.object(
            ra.subprocess, "run", return_value=_fake_result(1, "not json at all")
        ):
            result = run_analyzer(".")
        self.assertIn("JSON 解析失败", result["error"])

    def test_empty_diagnostics(self):
        with mock.patch.object(
            ra.subprocess, "run", return_value=_fake_result(0, json.dumps({"diagnostics": []}))
        ):
            result = run_analyzer(".")
        self.assertEqual(result["total"], 0)
        self.assertIsNone(result["error"])


class TestCli(unittest.TestCase):
    def _run(self, argv, **patch_kwargs):
        buf = io.StringIO()
        with mock.patch.object(ra.subprocess, "run", return_value=_fake_result(**patch_kwargs)):
            with redirect_stdout(buf):
                code = main(argv)
        return code, buf.getvalue()

    def test_exit_0_no_issues(self):
        code, out = self._run(["."], returncode=0, stdout=json.dumps({"diagnostics": []}))
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out)["total"], 0)

    def test_exit_1_with_errors(self):
        code, _ = self._run(["."], returncode=1, stdout=_diagnostics_payload())
        self.assertEqual(code, 1)

    def test_exit_2_warnings_only(self):
        payload = json.dumps(
            {"diagnostics": [{"severity": "WARNING", "code": "unused_import"}]}
        )
        code, _ = self._run(["."], returncode=2, stdout=payload)
        self.assertEqual(code, 2)

    def test_exit_3_infos_only(self):
        payload = json.dumps(
            {"diagnostics": [{"severity": "INFO", "code": "prefer_single_quotes"}]}
        )
        code, _ = self._run(["."], returncode=3, stdout=payload)
        self.assertEqual(code, 3)

    def test_exit_1_tool_failure(self):
        code, _ = self._run(["."], returncode=69, stdout="", stderr="boom")
        self.assertEqual(code, 1)


if __name__ == "__main__":
    unittest.main()
