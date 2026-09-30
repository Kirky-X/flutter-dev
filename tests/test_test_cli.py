#!/usr/bin/env python3
"""test/cli 冒烟级离线测试。

覆盖 build_run_plan 命令拼装、config 动作输出、argparse 路由与退出码；
run 动作真实执行需要 flutter CLI（记入 tests/SKIPPED.md），
此处覆盖 --dry-run 计划生成与 mock subprocess 的退出码透传。
"""
import io
import json
import os
import subprocess
import sys
import unittest
from contextlib import redirect_stderr, redirect_stdout
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from scripts.test import cli as test_cli
from scripts.test.cli import build_run_plan, cmd_config, main


class TestBuildRunPlan(unittest.TestCase):
    def test_unit_plan_no_file(self):
        with mock.patch.object(test_cli, "check_flutter_installed", return_value=True):
            plan = build_run_plan("/proj")
        self.assertEqual(plan["workflow"], "unit_widget_test")
        self.assertEqual(plan["command"], ["flutter", "test"])
        self.assertEqual(plan["cwd"], "/proj")
        self.assertEqual(plan["warnings"], [])

    def test_unit_plan_with_file(self):
        with mock.patch.object(test_cli, "check_flutter_installed", return_value=True):
            plan = build_run_plan("/proj", test_file="test/widget_test.dart")
        self.assertEqual(plan["command"], ["flutter", "test", "test/widget_test.dart"])

    def test_integration_plan_prefixes_dir(self):
        with mock.patch.object(test_cli, "check_flutter_installed", return_value=True):
            plan = build_run_plan("/proj", integration=True, test_file="app_test.dart")
        self.assertEqual(plan["workflow"], "integration_test")
        self.assertEqual(plan["command"], ["flutter", "test", "integration_test/app_test.dart"])

    def test_integration_plan_keeps_explicit_path(self):
        with mock.patch.object(test_cli, "check_flutter_installed", return_value=True):
            plan = build_run_plan(
                "/proj", integration=True, test_file="integration_test/app_test.dart"
            )
        self.assertEqual(plan["command"], ["flutter", "test", "integration_test/app_test.dart"])

    def test_coverage_and_extra_args(self):
        with mock.patch.object(test_cli, "check_flutter_installed", return_value=True):
            plan = build_run_plan(
                "/proj", coverage=True, extra_args=["--name", "MyTest"]
            )
        self.assertEqual(
            plan["command"], ["flutter", "test", "--coverage", "--name", "MyTest"]
        )
        self.assertTrue(plan["coverage"])

    def test_warning_when_flutter_missing(self):
        with mock.patch.object(test_cli, "check_flutter_installed", return_value=False):
            plan = build_run_plan("/proj")
        self.assertEqual(len(plan["warnings"]), 1)
        self.assertIn("flutter CLI 未检测到", plan["warnings"][0])


class TestCmdConfig(unittest.TestCase):
    def test_config_output_and_exit(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            code = cmd_config("/proj", coverage=True)
        self.assertEqual(code, 0)
        cfg = json.loads(buf.getvalue())
        self.assertEqual(cfg["project_path"], "/proj")
        self.assertTrue(cfg["coverage"])


class TestCliMain(unittest.TestCase):
    def _run(self, argv):
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = main(argv)
        return code, out.getvalue(), err.getvalue()

    def test_no_action_exit_2(self):
        code, _, _ = self._run([])
        self.assertEqual(code, 2)

    def test_invalid_action_exit_2(self):
        code, _, _ = self._run(["bogus"])
        self.assertEqual(code, 2)

    def test_config_action(self):
        code, out, _ = self._run(["config", "--project-path", "/proj"])
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out)["project_path"], "/proj")

    def test_run_dry_run_outputs_plan(self):
        with mock.patch.object(test_cli, "check_flutter_installed", return_value=True):
            code, out, _ = self._run(["run", "--project-path", "/proj", "--dry-run"])
        self.assertEqual(code, 0)
        plan = json.loads(out)
        self.assertEqual(plan["workflow"], "unit_widget_test")
        self.assertEqual(plan["warnings"], [])

    def test_run_exec_success_passthrough(self):
        fake = mock.Mock(returncode=0)
        with mock.patch.object(test_cli, "check_flutter_installed", return_value=True):
            with mock.patch.object(
                test_cli.subprocess, "run", return_value=fake
            ) as run_mock:
                code, _, _ = self._run(["run", "--project-path", "/proj"])
        self.assertEqual(code, 0)
        run_mock.assert_called_once_with(["flutter", "test"], cwd="/proj")

    def test_run_exec_failure_passthrough_exit_code(self):
        fake = mock.Mock(returncode=5)
        with mock.patch.object(test_cli, "check_flutter_installed", return_value=True):
            with mock.patch.object(test_cli.subprocess, "run", return_value=fake):
                code, _, err = self._run(["run", "--project-path", "/proj"])
        self.assertEqual(code, 5)
        self.assertIn("flutter test 失败 (exit=5)", err)

    def test_run_flutter_not_found_exit_127(self):
        with mock.patch.object(test_cli, "check_flutter_installed", return_value=True):
            with mock.patch.object(
                test_cli.subprocess, "run", side_effect=FileNotFoundError("no flutter")
            ):
                code, _, err = self._run(["run", "--project-path", "/proj"])
        self.assertEqual(code, 127)
        self.assertIn("flutter CLI 未找到", err)


if __name__ == "__main__":
    unittest.main()
