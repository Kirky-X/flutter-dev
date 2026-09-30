#!/usr/bin/env python3
"""search 冒烟级离线测试（本地 sidebars 关键词匹配，无网络）。

用临时 sidebars 目录做 fixture，覆盖打分函数、doc_type 过滤、
错误显性化与 CLI 退出码。
"""
import io
import json
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stdout

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from scripts.search.search import _score_title, main, search

FIXTURE_SIDEBAR = {
    "flutter-docs.md": """## Widgets

## 1. [ListView class](https://example.dev/flutter/widgets/ListView-class.html)
### 1.1. [ListView builder](https://example.dev/flutter/widgets/ListView-builder.html)
## 2. [GridView class](https://example.dev/flutter/widgets/GridView-class.html)
""",
    "flutter-api.md": """## API

## 1. [ListView](https://example.dev/api/ListView.html)
""",
    "flutter-ai-docs.md": """## AI

## 1. [Understanding ListView](https://example.dev/ai/listview.html)
""",
}


def _make_sidebars(tmp: str) -> str:
    for fname, content in FIXTURE_SIDEBAR.items():
        with open(os.path.join(tmp, fname), "w", encoding="utf-8") as fh:
            fh.write(content)
    return tmp


class TestScoreTitle(unittest.TestCase):
    def test_exact(self):
        self.assertEqual(_score_title("ListView", "ListView"), 100)

    def test_case_insensitive_exact(self):
        self.assertEqual(_score_title("listview", "ListView"), 100)

    def test_startswith(self):
        self.assertEqual(_score_title("ListView", "ListView builder"), 80)

    def test_contains(self):
        self.assertEqual(_score_title("View", "GridView class"), 60)

    def test_all_tokens(self):
        self.assertEqual(_score_title("grid class", "GridView class"), 40)

    def test_any_token(self):
        self.assertEqual(_score_title("grid missing", "GridView class"), 20)

    def test_no_match(self):
        self.assertEqual(_score_title("Row", "GridView class"), 0)

    def test_empty_inputs(self):
        self.assertEqual(_score_title("", "x"), 0)
        self.assertEqual(_score_title("x", ""), 0)


class TestSearch(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.sidebars = _make_sidebars(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def test_basic_match_sorted_by_score(self):
        result = search("ListView", sidebars_dir=self.sidebars)
        # docs 3 条 + api 精确匹配 1 条
        self.assertEqual(result["total"], 4)
        titles = [r["title"] for r in result["results"]]
        # 精确匹配(100) > startswith(80) > contains(60)；同分按 title 字母序
        self.assertEqual(titles[0], "ListView")
        self.assertEqual(
            sorted(titles[1:]),
            ["ListView builder", "ListView class", "Understanding ListView"],
        )

    def test_doc_type_docs_filter(self):
        result = search("ListView", doc_type="docs", sidebars_dir=self.sidebars)
        # GridView 不含关键词，docs 侧边栏命中 2 条
        self.assertEqual(result["total"], 2)
        self.assertTrue(all(r["doc_type"] == "docs" for r in result["results"]))

    def test_doc_type_filter(self):
        result = search("ListView", doc_type="api", sidebars_dir=self.sidebars)
        self.assertEqual(result["total"], 1)
        self.assertEqual(result["results"][0]["url"], "https://example.dev/api/ListView.html")

    def test_top_k_truncation(self):
        result = search("ListView", top_k=1, sidebars_dir=self.sidebars)
        self.assertEqual(result["total"], 4)
        self.assertEqual(len(result["results"]), 1)

    def test_no_match_empty_results(self):
        result = search("NonexistentWidget", sidebars_dir=self.sidebars)
        self.assertEqual(result["total"], 0)
        self.assertEqual(result["results"], [])
        self.assertEqual(result["errors"], [])

    def test_missing_doc_type_sidebar_reported(self):
        os.unlink(os.path.join(self.sidebars, "flutter-api.md"))
        result = search("ListView", doc_type="api", sidebars_dir=self.sidebars)
        self.assertEqual(result["results"], [])
        self.assertTrue(any("flutter-api.md" in e for e in result["errors"]))

    def test_missing_dir_all_doc_types(self):
        result = search("ListView", sidebars_dir=os.path.join(self.sidebars, "nope"))
        self.assertEqual(result["results"], [])
        self.assertTrue(result["errors"])

    def test_invalid_args_raise(self):
        with self.assertRaises(ValueError):
            search("   ", sidebars_dir=self.sidebars)
        with self.assertRaises(ValueError):
            search("x", top_k=0, sidebars_dir=self.sidebars)
        with self.assertRaises(ValueError):
            search("x", top_k=101, sidebars_dir=self.sidebars)
        with self.assertRaises(ValueError):
            search("x", doc_type="wiki", sidebars_dir=self.sidebars)


class TestCli(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.sidebars = _make_sidebars(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def _run(self, argv):
        buf = io.StringIO()
        with redirect_stdout(buf):
            code = main(argv)
        return code, buf.getvalue()

    def test_search_exit_0(self):
        code, out = self._run(["ListView", "--sidebars-dir", self.sidebars])
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out)["total"], 4)

    def test_zero_match_with_missing_sidebar_exit_1(self):
        code, _ = self._run(
            ["ListView", "--doc-type", "api", "--sidebars-dir", os.path.join(self.sidebars, "no")]
        )
        self.assertEqual(code, 1)

    def test_invalid_doc_type_exit_2(self):
        code, _ = self._run(["ListView", "--doc-type", "wiki", "--sidebars-dir", self.sidebars])
        self.assertEqual(code, 2)


if __name__ == "__main__":
    unittest.main()
