#!/usr/bin/env python3
"""parse_stack_trace 冒烟级离线测试（纯函数 + CLI 退出码，无网络/无工具链依赖）。"""
import io
import json
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stdout

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from scripts.fix.parse_stack_trace import extract_error_header, main, parse_stack_trace

SAMPLE = (
    "Unhandled exception:\n"
    "NoSuchMethodError: The method 'foo' was called on null.\n"
    "#0      main (file:///app/main.dart:7:3)\n"
    "#1      _MyHomePageState.build (package:myapp/home.dart:42:5)\n"
    "#2      <asynchronous suspension>\n"
)


class TestExtractErrorHeader(unittest.TestCase):
    def test_basic(self):
        self.assertEqual(
            extract_error_header("TypeError: foo is not a function"),
            ("TypeError", "foo is not a function"),
        )

    def test_unhandled_prefix(self):
        etype, msg = extract_error_header(
            "Unhandled exception: StateError: Bad state: no element"
        )
        self.assertEqual(etype, "StateError")
        self.assertEqual(msg, "Bad state: no element")

    def test_no_match(self):
        self.assertEqual(extract_error_header("just some log line"), ("", ""))

    def test_empty(self):
        self.assertEqual(extract_error_header(""), ("", ""))


class TestParseStackTrace(unittest.TestCase):
    def test_detected_fields(self):
        result = parse_stack_trace(SAMPLE)
        self.assertEqual(result["status"], "detected")
        self.assertEqual(result["error_type"], "NoSuchMethodError")
        self.assertEqual(
            result["error_message"], "The method 'foo' was called on null."
        )
        self.assertEqual(len(result["stack"]), 2)
        top = result["top_frame"]
        self.assertEqual(top["function"], "main")
        self.assertEqual(top["file"], "file:///app/main.dart")
        self.assertEqual(top["line"], 7)
        self.assertEqual(top["column"], 3)
        self.assertEqual(result["suspected_file"], "file:///app/main.dart")
        self.assertIn("栈顶帧", result["next_action"])

    def test_package_frame_extraction(self):
        result = parse_stack_trace(SAMPLE)
        pkg_frame = result["stack"][1]
        self.assertEqual(pkg_frame["package"], "myapp")
        self.assertEqual(pkg_frame["file"], "package:myapp/home.dart")
        self.assertEqual(pkg_frame["line"], 42)
        self.assertEqual(pkg_frame["column"], 5)

    def test_keywords_dedupe_and_priority(self):
        result = parse_stack_trace(SAMPLE)
        # 错误类型优先，其次 message 前 3 个标识符，去重保序
        self.assertEqual(
            result["keywords"], ["NoSuchMethodError", "The", "method", "foo"]
        )

    def test_no_stack_trace(self):
        result = parse_stack_trace("some random log without frames")
        self.assertEqual(result["status"], "no_stack_trace")
        self.assertIsNone(result["top_frame"])
        self.assertEqual(result["stack"], [])

    def test_empty_input_parse_failed(self):
        result = parse_stack_trace("   ")
        self.assertEqual(result["status"], "parse_failed")
        self.assertIsNone(result["top_frame"])

    def test_column_optional(self):
        result = parse_stack_trace("#0  f (dart:core:100)")
        self.assertEqual(result["status"], "detected")
        self.assertEqual(result["top_frame"]["line"], 100)
        self.assertEqual(result["top_frame"]["column"], 0)


class TestCli(unittest.TestCase):
    def _run(self, argv):
        buf = io.StringIO()
        with redirect_stdout(buf):
            code = main(argv)
        return code, buf.getvalue()

    def test_detected_exit_0(self):
        code, out = self._run(["--log-text", SAMPLE])
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out)["status"], "detected")

    def test_no_stack_trace_exit_1(self):
        code, _ = self._run(["--log-text", "no frames here"])
        self.assertEqual(code, 1)

    def test_empty_text_exit_2(self):
        code, _ = self._run(["--log-text", ""])
        self.assertEqual(code, 2)

    def test_log_file_ok(self):
        with tempfile.NamedTemporaryFile(
            "w", suffix=".log", delete=False, encoding="utf-8"
        ) as fh:
            fh.write(SAMPLE)
            path = fh.name
        try:
            code, out = self._run(["--log-file", path])
            self.assertEqual(code, 0)
            self.assertEqual(json.loads(out)["source"], "file")
        finally:
            os.unlink(path)

    def test_log_file_missing_exit_2(self):
        code, _ = self._run(["--log-file", "/nonexistent/dir/crash.log"])
        self.assertEqual(code, 2)

    def test_missing_required_arg_exit_2(self):
        code, _ = self._run([])
        self.assertEqual(code, 2)

    def test_mutually_exclusive_exit_2(self):
        code, _ = self._run(["--log-text", "a", "--log-file", "b"])
        self.assertEqual(code, 2)


CONSOLE_SAMPLE = (
    "E/Flutter ( 1234): Unhandled exception:\n"
    "E/Flutter ( 1234): NoSuchMethodError: The method 'foo' was called on null.\n"
    "E/Flutter ( 1234): #0      HomePage.build (package:myapp/pages/home.dart:42:13)\n"
    "E/Flutter ( 1234): #1      StatefulElement.build (package:flutter/src/widgets/framework.dart:5224:46)\n"
)

BARE_PREFIX_SAMPLE = (
    "E NoSuchMethodError: The method 'foo' was called on null.\n"
    "E #0      HomePage.build (package:myapp/pages/home.dart:42:13)\n"
)


class TestConsolePrefix(unittest.TestCase):
    """flutter run / flutter test 控制台日志行前缀（`E/Flutter ( pid): `、`E `）。"""

    def test_logcat_style_prefix_detected(self):
        result = parse_stack_trace(CONSOLE_SAMPLE)
        self.assertEqual(result["status"], "detected")
        self.assertEqual(result["error_type"], "NoSuchMethodError")
        self.assertEqual(
            result["error_message"], "The method 'foo' was called on null."
        )
        top = result["top_frame"]
        self.assertEqual(top["function"], "HomePage.build")
        self.assertEqual(top["file"], "package:myapp/pages/home.dart")
        self.assertEqual(top["line"], 42)
        self.assertEqual(top["column"], 13)

    def test_bare_level_prefix_detected(self):
        result = parse_stack_trace(BARE_PREFIX_SAMPLE)
        self.assertEqual(result["status"], "detected")
        self.assertEqual(result["error_type"], "NoSuchMethodError")
        self.assertEqual(result["top_frame"]["line"], 42)

    def test_standard_format_unaffected(self):
        result = parse_stack_trace(SAMPLE)
        self.assertEqual(result["status"], "detected")
        self.assertEqual(result["error_type"], "NoSuchMethodError")
        self.assertEqual(len(result["stack"]), 2)


if __name__ == "__main__":
    unittest.main()
