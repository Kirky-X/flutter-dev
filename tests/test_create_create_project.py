#!/usr/bin/env python3
"""create_project 冒烟级离线测试。

校验逻辑（项目名/组织名/平台/输出目录预检查）为纯函数路径真实测试；
`flutter create` 本体需要 Flutter SDK（记入 tests/SKIPPED.md），成功/失败/
超时路径用 mock subprocess 覆盖命令拼装与错误显性化。
"""
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from scripts.create import create_project as cp
from scripts.create.create_project import main


class TestValidation(unittest.TestCase):
    def test_valid_name_passes_validation(self):
        # 输出目录不存在 → 走到 subprocess 调用前不会抛 ValueError；
        # 用 mock 拦截 subprocess 验证校验通过后命令正确拼装。
        with mock.patch.object(
            cp.subprocess, "run", return_value=mock.Mock(returncode=0, stdout="", stderr="")
        ):
            result = cp.create_project("my_app", "/tmp/does-not-matter")
        self.assertEqual(result["created"], "my_app")
        self.assertEqual(result["platforms"], "all")
        self.assertEqual(result["org"], "com.example")

    def test_invalid_names(self):
        for bad in ("MyApp", "1app", "my-app", "my app", ""):
            with self.assertRaises(ValueError):
                cp.create_project(bad, "/tmp/x")

    def test_invalid_org(self):
        for bad in ("com example", "Com.Example", "example", "com."):
            with self.assertRaises(ValueError):
                cp.create_project("app", "/tmp/x", org=bad)

    def test_unknown_platform_lists_valid(self):
        with self.assertRaises(ValueError) as ctx:
            cp.create_project("app", "/tmp/x", platforms=["android", "symbian"])
        self.assertIn("symbian", str(ctx.exception))
        self.assertIn("android", str(ctx.exception))

    def test_existing_nonempty_dir_requires_force(self):
        with tempfile.TemporaryDirectory() as tmp:
            with open(os.path.join(tmp, "keep.txt"), "w", encoding="utf-8") as fh:
                fh.write("data")
            with self.assertRaises(ValueError) as ctx:
                cp.create_project("app", tmp)
            self.assertIn("--force", str(ctx.exception))

    def test_empty_existing_dir_is_allowed(self):
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.object(
                cp.subprocess,
                "run",
                return_value=mock.Mock(returncode=0, stdout="", stderr=""),
            ) as run_mock:
                result = cp.create_project("app", tmp)
        self.assertEqual(result["created"], "app")
        run_mock.assert_called_once()


class TestSubprocessPaths(unittest.TestCase):
    def test_command_construction(self):
        with mock.patch.object(
            cp.subprocess, "run", return_value=mock.Mock(returncode=0, stdout="", stderr="")
        ) as run_mock:
            cp.create_project(
                "shop",
                "/tmp/out",
                platforms=["android", "ios"],
                org="com.example",
                force=True,
            )
        cmd = run_mock.call_args.args[0]
        self.assertEqual(
            cmd,
            [
                "flutter",
                "create",
                "--project-name",
                "shop",
                "--org",
                "com.example",
                "--platforms",
                "android,ios",
                "/tmp/out",
            ],
        )

    def test_nonzero_exit_raises_runtimeerror_with_stderr(self):
        with mock.patch.object(
            cp.subprocess,
            "run",
            return_value=mock.Mock(returncode=1, stdout="", stderr="SDK not found"),
        ):
            with self.assertRaises(RuntimeError) as ctx:
                cp.create_project("app", "/tmp/x")
        self.assertIn("SDK not found", str(ctx.exception))

    def test_timeout_raises_runtimeerror(self):
        with mock.patch.object(
            cp.subprocess, "run", side_effect=subprocess.TimeoutExpired(cmd="flutter", timeout=300)
        ):
            with self.assertRaises(RuntimeError) as ctx:
                cp.create_project("app", "/tmp/x")
        self.assertIn("超时", str(ctx.exception))

    def test_flutter_not_found_raises_runtimeerror(self):
        with mock.patch.object(
            cp.subprocess,
            "run",
            side_effect=FileNotFoundError(2, "No such file or directory: 'flutter'"),
        ):
            with self.assertRaises(RuntimeError) as ctx:
                cp.create_project("app", "/tmp/x")
        self.assertIn("flutter CLI 未找到", str(ctx.exception))


class TestCli(unittest.TestCase):
    def _run(self, argv, **run_kwargs):
        buf = io.StringIO()
        default = mock.Mock(returncode=0, stdout="", stderr="")
        with mock.patch.object(cp.subprocess, "run", return_value=run_kwargs.pop("result", default)):
            with redirect_stdout(buf):
                code = main(argv)
        return code, buf.getvalue()

    def test_success_exit_0(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = os.path.join(tmp, "fresh")
            code, out_text = self._run(["--name", "my_app", "--out", out])
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out_text)["created"], "my_app")

    def test_invalid_name_exit_2(self):
        code, _ = self._run(["--name", "MyApp", "--out", "/tmp/x"])
        self.assertEqual(code, 2)

    def test_existing_dir_exit_2(self):
        with tempfile.TemporaryDirectory() as tmp:
            with open(os.path.join(tmp, "f.txt"), "w", encoding="utf-8") as fh:
                fh.write("x")
            code, _ = self._run(["--name", "app", "--out", tmp])
        self.assertEqual(code, 2)

    def test_flutter_failure_exit_1(self):
        fail = mock.Mock(returncode=1, stdout="", stderr="create failed")
        code, _ = self._run(["--name", "app", "--out", "/tmp/x"], result=fail)
        self.assertEqual(code, 1)

    def test_missing_required_args_exit_2(self):
        code, _ = self._run(["--name", "app"])
        self.assertEqual(code, 2)


if __name__ == "__main__":
    unittest.main()
