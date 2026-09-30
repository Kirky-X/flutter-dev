#!/usr/bin/env python3
"""test/platform 冒烟级离线测试。

平台检测/工具启用策略/测试配置生成为纯函数路径真实测试；
flutter/dart CLI 探测需要真实 SDK（记入 tests/SKIPPED.md），
此处用 mock subprocess 覆盖版本解析与未安装错误路径。
"""
import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from scripts.test import platform as pf


class TestDetectPlatform(unittest.TestCase):
    def test_known_platforms(self):
        cases = {"linux": "linux", "win32": "windows", "darwin": "macos"}
        for raw, expected in cases.items():
            with mock.patch("sys.platform", raw):
                self.assertEqual(pf.detect_platform(), expected)

    def test_unknown_platform_raises(self):
        with mock.patch("sys.platform", "sunos5"):
            with self.assertRaises(ValueError):
                pf.detect_platform()


class TestEnabledTools(unittest.TestCase):
    _EXPECTED = ["flutter_test", "flutter_integration_test", "dart_analyze", "flutter_build"]

    def test_all_platforms_full_tools(self):
        for name in ("linux", "windows", "macos"):
            self.assertEqual(pf.enabled_tools(name), self._EXPECTED)

    def test_default_uses_detect_platform(self):
        with mock.patch("sys.platform", "linux"):
            self.assertEqual(pf.enabled_tools(), self._EXPECTED)

    def test_unknown_platform_raises(self):
        with self.assertRaises(ValueError):
            pf.enabled_tools("dos")

    def test_disabled_hint_always_empty(self):
        self.assertEqual(pf.disabled_tools_hint("linux"), "")


class TestGenerateTestConfig(unittest.TestCase):
    def test_default_config(self):
        cfg = pf.generate_test_config("/proj")
        self.assertEqual(cfg["test_command"], ["flutter", "test"])
        self.assertEqual(
            cfg["integration_command"], ["flutter", "test", "integration_test"]
        )
        self.assertFalse(cfg["coverage"])
        self.assertIsNone(cfg["coverage_file"])

    def test_coverage_config(self):
        cfg = pf.generate_test_config("/proj", coverage=True)
        self.assertIn("--coverage", cfg["test_command"])
        self.assertIn("--coverage", cfg["integration_command"])
        self.assertEqual(cfg["coverage_file"], "coverage/lcov.info")

    def test_custom_integration_dir(self):
        cfg = pf.generate_test_config("/proj", integration_test_dir="itests")
        self.assertEqual(cfg["integration_command"], ["flutter", "test", "itests"])
        self.assertEqual(cfg["integration_test_dir"], "itests")


class TestDetectFlutter(unittest.TestCase):
    def test_flutter_output_contains_both_versions(self):
        stdout = (
            "Flutter 3.19.5 • channel stable • https://github.com/flutter/flutter.git\n"
            "Tools • Dart 3.3.3 • DevTools 2.33.1\n"
        )
        with mock.patch.object(
            pf, "_run_version_cmd", return_value=(0, stdout, "")
        ) as runner:
            result = pf.detect_flutter()
        runner.assert_called_once_with(["flutter", "--version"])
        self.assertTrue(result["flutter"]["installed"])
        self.assertEqual(result["flutter"]["version"], "3.19.5")
        self.assertEqual(result["flutter"]["channel"], "stable")
        self.assertTrue(result["dart"]["installed"])
        self.assertEqual(result["dart"]["version"], "3.3.3")
        self.assertIsNone(result["error"])

    def test_flutter_missing_dart_fallback(self):
        outputs = iter(
            [
                (-1, "", "not found"),
                (0, "Dart SDK version: 3.4.0 (stable)", ""),
            ]
        )
        with mock.patch.object(pf, "_run_version_cmd", side_effect=lambda cmd: next(outputs)):
            result = pf.detect_flutter()
        self.assertFalse(result["flutter"]["installed"])
        self.assertTrue(result["dart"]["installed"])
        self.assertEqual(result["dart"]["version"], "3.4.0")
        self.assertIn("flutter CLI 未找到", result["error"])

    def test_both_missing_error_visible(self):
        with mock.patch.object(pf, "_run_version_cmd", return_value=(-1, "", "nope")):
            result = pf.detect_flutter()
        self.assertFalse(result["flutter"]["installed"])
        self.assertFalse(result["dart"]["installed"])
        self.assertIn("flutter CLI 未找到", result["error"])
        self.assertIn("dart CLI 未找到", result["error"])

    def test_flutter_nonzero_exit_reported(self):
        with mock.patch.object(pf, "_run_version_cmd", return_value=(1, "", "crash")):
            result = pf.detect_flutter()
        self.assertIn("flutter --version 失败 (exit=1)", result["error"])


class TestCheckFlutterInstalled(unittest.TestCase):
    def test_which_none(self):
        with mock.patch.object(pf.shutil, "which", return_value=None):
            self.assertFalse(pf.check_flutter_installed())

    def test_which_found_and_version_ok(self):
        fake = mock.Mock(returncode=0, stdout="", stderr="")
        with mock.patch.object(pf.shutil, "which", return_value="/usr/bin/flutter"):
            with mock.patch.object(pf.subprocess, "run", return_value=fake):
                self.assertTrue(pf.check_flutter_installed())

    def test_which_found_but_version_fails(self):
        fake = mock.Mock(returncode=1, stdout="", stderr="broken")
        with mock.patch.object(pf.shutil, "which", return_value="/usr/bin/flutter"):
            with mock.patch.object(pf.subprocess, "run", return_value=fake):
                self.assertFalse(pf.check_flutter_installed())


if __name__ == "__main__":
    unittest.main()
