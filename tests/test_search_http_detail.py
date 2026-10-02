#!/usr/bin/env python3
"""_http + detail 冒烟级离线测试。

覆盖 html_to_markdown 转换、实体解码、endpoint 路由、http_get 错误路径
（mock httpx 客户端）、extract_title 提取、SSRF 域名白名单（真实离线路径）。
真实网络抓取 docs.flutter.cn 记入 tests/SKIPPED.md。
"""
import io
import json
import os
import sys
import unittest
from contextlib import redirect_stdout
from unittest import mock

import httpx

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from scripts.search._http import (
    COMMON_HEADERS,
    TIMEOUT,
    endpoint_url,
    html_to_markdown,
    http_get,
)
from scripts.search.detail import detail, extract_title, main as detail_main


class TestHtmlToMarkdown(unittest.TestCase):
    def test_empty(self):
        self.assertEqual(html_to_markdown(""), "")
        self.assertEqual(html_to_markdown("   \n "), "")

    def test_heading_and_emphasis(self):
        md = html_to_markdown("<h2>Install</h2><p>Hello <strong>world</strong></p>")
        self.assertIn("## Install", md)
        self.assertIn("**world**", md)

    def test_pre_block_preserved(self):
        md = html_to_markdown("<pre><code>int x = 1;</code></pre>")
        self.assertIn("```\nint x = 1;\n```", md)

    def test_inline_code(self):
        md = html_to_markdown("<p>use <code>setState()</code> here</p>")
        self.assertIn("`setState()`", md)

    def test_table(self):
        html = "<table><tr><th>A</th><th>B</th></tr><tr><td>1</td><td>2</td></tr></table>"
        md = html_to_markdown(html)
        self.assertIn("| A | B |", md)
        self.assertIn("| 1 | 2 |", md)
        self.assertIn("| - | - |", md)

    def test_lists(self):
        self.assertIn("- a\n- b", html_to_markdown("<ul><li>a</li><li>b</li></ul>"))
        self.assertIn("1. a\n2. b", html_to_markdown("<ol><li>a</li><li>b</li></ol>"))

    def test_link(self):
        md = html_to_markdown('<a href="https://x.dev">docs</a>')
        self.assertIn("[docs](https://x.dev)", md)

    def test_script_style_stripped(self):
        md = html_to_markdown("<script>alert(1)</script><style>.x{}</style>kept")
        self.assertNotIn("alert", md)
        self.assertNotIn(".x{}", md)
        self.assertIn("kept", md)

    def test_material_icon_ligature_stripped(self):
        md = html_to_markdown(
            '<a href="/ui">UI</a>'
            '<span class="material-symbols" aria-hidden="true">chevron_right</span>'
            '<a href="/ui/layout">Layout</a>'
        )
        self.assertNotIn("chevron_right", md)
        self.assertIn("[UI](/ui)", md)
        self.assertIn("[Layout](/ui/layout)", md)

    def test_icon_name_inside_pre_survives(self):
        md = html_to_markdown("<pre><code>Icon(Icons.chevron_right)</code></pre>")
        self.assertIn("chevron_right", md)
        self.assertIn("Icon(Icons.chevron_right)", md)

    def test_main_body_preferred_over_nav(self):
        html = (
            "<html><body><nav><a href='/nav'>SiteNav</a></nav>"
            "<main><h1>Real Body</h1><p>content</p></main>"
            "<footer>FooterStuff</footer></body></html>"
        )
        md = html_to_markdown(html)
        self.assertIn("Real Body", md)
        self.assertNotIn("SiteNav", md)
        self.assertNotIn("FooterStuff", md)

    def test_no_main_falls_back_to_whole_document(self):
        md = html_to_markdown("<div><p>plain fragment</p></div>")
        self.assertEqual(md, "plain fragment")

    def test_entities(self):
        self.assertEqual(html_to_markdown("a &amp; b &lt; c &#65; &#x42;"), "a & b < c A B")

    def test_invalid_entity_preserved(self):
        text = "value &#999999999999; end"
        self.assertEqual(html_to_markdown(text), text)


class TestEndpointUrl(unittest.TestCase):
    def test_valid_endpoints(self):
        for endpoint in ("docs", "api", "pub"):
            self.assertTrue(endpoint_url(endpoint).startswith("https://"))

    def test_unknown_endpoint_raises(self):
        with self.assertRaises(ValueError):
            endpoint_url("wiki")


class TestHttpGet(unittest.TestCase):
    def _client(self, **kwargs):
        client = mock.Mock(spec=httpx.Client)
        resp = mock.Mock(spec=httpx.Response)
        resp.text = "page body"
        resp.raise_for_status.return_value = None
        client.get.return_value = resp
        for name, value in kwargs.items():
            getattr(client, name).side_effect = value
        return client

    def test_success(self):
        text, err = http_get("https://docs.flutter.dev/x", client=self._client())
        self.assertEqual(text, "page body")
        self.assertIsNone(err)

    def test_http_error_surfaced(self):
        client = self._client(get=httpx.ConnectError("boom"))
        text, err = http_get("https://docs.flutter.dev/x", client=client)
        self.assertEqual(text, "")
        self.assertIn("HTTP GET failed", err)
        self.assertIn("boom", err)

    def test_empty_url(self):
        text, err = http_get("   ", client=self._client())
        self.assertEqual(text, "")
        self.assertEqual(err, "url must not be empty")

    def test_defaults_exported(self):
        self.assertIn("user-agent", COMMON_HEADERS)
        self.assertGreater(TIMEOUT, 0)


class TestExtractTitle(unittest.TestCase):
    def test_title_tag_with_suffix(self):
        self.assertEqual(extract_title("<title>ListView class | Flutter</title>"), "ListView class")

    def test_title_kept_when_suffix_only_content(self):
        self.assertEqual(extract_title("<title> | Flutter</title>"), "| Flutter")

    def test_h1_fallback(self):
        self.assertEqual(extract_title("<h1>GridView</h1>"), "GridView")

    def test_h1_strips_tags(self):
        self.assertEqual(extract_title("<h1><code>Row</code> widget</h1>"), "Row widget")

    def test_empty(self):
        self.assertEqual(extract_title(""), "")
        self.assertEqual(extract_title("<p>no title</p>"), "")


class TestDetail(unittest.TestCase):
    def test_ssrf_blocked_offline(self):
        for url in ("http://169.254.169.254/latest/meta-data", "https://evil.example.com/page"):
            result = detail(url)
            self.assertIn("SSRF", result["error"])
            self.assertEqual(result["content"], "")
            self.assertEqual(result["title"], "")

    def test_empty_url_raises(self):
        with self.assertRaises(ValueError):
            detail("   ")

    def test_http_error_path(self):
        with mock.patch(
            "scripts.search.detail.http_get", return_value=("", "HTTP GET failed for x")
        ):
            result = detail("https://docs.flutter.cn/ui")
        self.assertEqual(result["error"], "HTTP GET failed for x")
        self.assertEqual(result["content"], "")

    def test_empty_body(self):
        with mock.patch("scripts.search.detail.http_get", return_value=("   ", None)):
            result = detail("https://docs.flutter.cn/ui")
        self.assertIn("empty response body", result["error"])

    def test_success_with_main_extraction(self):
        html = (
            "<html><head><title>MyPage | Flutter</title>"
            '<meta name="description" content="A page about layouts"></head>'
            "<body><nav>Menu noise</nav>"
            "<main><p>Main body text</p></main></body></html>"
        )
        with mock.patch("scripts.search.detail.http_get", return_value=(html, None)):
            result = detail("https://docs.flutter.cn/ui/layout")
        self.assertIsNone(result["error"])
        self.assertEqual(result["title"], "MyPage")
        self.assertEqual(result["description"], "A page about layouts")
        self.assertIn("Main body text", result["content"])
        self.assertNotIn("Menu noise", result["content"])

    def test_main_fallback_to_full_html(self):
        html = "<html><title>T</title><p>only body</p></html>"
        with mock.patch("scripts.search.detail.http_get", return_value=(html, None)):
            result = detail("https://docs.flutter.cn/x")
        self.assertIn("only body", result["content"])


class TestCli(unittest.TestCase):
    def _run(self, argv):
        buf = io.StringIO()
        with redirect_stdout(buf):
            code = detail_main(argv)
        return code, buf.getvalue()

    def test_ssrf_exit_1(self):
        code, out = self._run(["https://evil.example.com/x"])
        self.assertEqual(code, 1)
        self.assertIn("SSRF", json.loads(out)["error"])

    def test_empty_url_exit_2(self):
        code, _ = self._run(["   "])
        self.assertEqual(code, 2)


if __name__ == "__main__":
    unittest.main()
