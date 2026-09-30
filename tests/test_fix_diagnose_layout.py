#!/usr/bin/env python3
"""diagnose_layout 冒烟级离线测试（六类 layout 错误模式 + CLI 退出码）。"""
import io
import json
import os
import sys
import unittest
from contextlib import redirect_stdout

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from scripts.fix.diagnose_layout import LAYOUT_FIX_DOC, diagnose_layout, main


class TestDiagnoseLayoutPatterns(unittest.TestCase):
    def test_renderflex_overflow_with_detail(self):
        result = diagnose_layout(
            "The following RenderFlex overflowed by 37 pixels on the right."
        )
        self.assertEqual(result["status"], "detected")
        self.assertEqual(result["error_type"], "RenderFlex overflowed")
        self.assertEqual(result["details"]["overflow_pixels"], "37")
        self.assertEqual(result["details"]["overflow_direction"], "right")

    def test_bottom_overflow_no_direction(self):
        result = diagnose_layout("Bottom overflowed by 12 pixels on startup.")
        self.assertEqual(result["status"], "detected")
        self.assertEqual(result["details"]["overflow_pixels"], "12")
        self.assertEqual(result["details"]["overflow_direction"], "")

    def test_unbounded_constraints(self):
        result = diagnose_layout(
            "RenderFlex children have non-zero flex but incoming width "
            "constraints are unbounded."
        )
        self.assertEqual(result["status"], "detected")
        self.assertEqual(result["error_type"], "Unbounded constraints")

    def test_no_material_widget(self):
        result = diagnose_layout("No Material widget found within ListTile.")
        self.assertEqual(result["status"], "detected")
        self.assertEqual(result["error_type"], "No Material widget found")

    def test_renderbox_exception(self):
        result = diagnose_layout("RenderBox was not laid out: RenderFlex#12345")
        self.assertEqual(result["status"], "detected")
        self.assertEqual(result["error_type"], "RenderBox layout exception")

    def test_parent_data_widget(self):
        result = diagnose_layout(
            "Incorrect use of ParentDataWidget. Expanded inside Container."
        )
        self.assertEqual(result["status"], "detected")
        self.assertEqual(result["error_type"], "Incorrect use of ParentDataWidget")

    def test_setstate_after_dispose(self):
        result = diagnose_layout("setState() called after dispose(): _State#abc")
        self.assertEqual(result["status"], "detected")
        self.assertEqual(result["error_type"], "setState() called after dispose")

    def test_case_insensitive(self):
        result = diagnose_layout("renderflex overflowed by 5 pixels on the bottom")
        self.assertEqual(result["status"], "detected")

    def test_common_fields(self):
        result = diagnose_layout("RenderFlex overflowed by 1 pixels on the right.")
        self.assertEqual(result["fix_doc"], LAYOUT_FIX_DOC)
        self.assertTrue(result["fix_suggestion"])
        self.assertIn(LAYOUT_FIX_DOC, result["next_action"])

    def test_no_layout_error(self):
        result = diagnose_layout("An unrelated error happened.")
        self.assertEqual(result["status"], "no_layout_error")
        self.assertEqual(result["error_type"], "")

    def test_empty_parse_failed(self):
        result = diagnose_layout("   ")
        self.assertEqual(result["status"], "parse_failed")


class TestCli(unittest.TestCase):
    def _run(self, argv):
        buf = io.StringIO()
        with redirect_stdout(buf):
            code = main(argv)
        return code, buf.getvalue()

    def test_detected_exit_0(self):
        code, out = self._run(["--log-text", "RenderFlex overflowed by 9 pixels on the right."])
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out)["status"], "detected")

    def test_no_layout_error_exit_1(self):
        code, _ = self._run(["--log-text", "nothing relevant"])
        self.assertEqual(code, 1)

    def test_empty_exit_2(self):
        code, _ = self._run(["--log-text", ""])
        self.assertEqual(code, 2)

    def test_missing_file_exit_2(self):
        code, _ = self._run(["--log-file", "/nonexistent/dir/layout.log"])
        self.assertEqual(code, 2)

    def test_no_args_exit_2(self):
        code, _ = self._run([])
        self.assertEqual(code, 2)


if __name__ == "__main__":
    unittest.main()
