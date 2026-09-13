"""B16: content_fetcher.py 抓取 Flutter 文档 url 网页内容为 markdown (Red phase).

flutter-dev 适配：detail(url) 直接接受 url（Flutter 文档是静态 HTML 站点），
不需要 hap-dev 的 URL_PATH_TO_CATALOG 白名单和 extract_object_id_and_catalog
（那是 HarmonyOS API 特有的 object_id+catalog 拆分逻辑）。

fetch_content(url) 调用 scripts.search.detail.detail(url) 获取 doc 内容
（HTML→Markdown），返回 str。detail() 返回 error 时 raise ValueError（fail-loud）。
"""
from __future__ import annotations

from unittest.mock import patch

import pytest

from scripts.kb.content_fetcher import (
    DEFAULT_EXPIRE_DAYS,
    fetch_content,
)


SAMPLE_URL = "https://docs.flutter.cn/ui/widgets/layout"


def test_fetch_content_returns_non_empty_str():
    """B16-1: 成功调用返回非空 markdown str。"""
    fake_result = {"content": "# 标题\n\n正文内容。", "error": None}
    with patch("scripts.kb.content_fetcher.detail", return_value=fake_result):
        content = fetch_content(SAMPLE_URL)
    assert isinstance(content, str)
    assert len(content) > 0
    assert "标题" in content


def test_fetch_content_propagates_detail_error_as_value_error():
    """B16-2: detail() 返回 {'error': ...} 时 raise ValueError（fail-loud）。"""
    fake_result = {"content": "", "error": "HTTP GET failed: 404"}
    with patch("scripts.kb.content_fetcher.detail", return_value=fake_result):
        with pytest.raises(ValueError, match="error|失败"):
            fetch_content(SAMPLE_URL)


def test_fetch_content_empty_url_raises():
    """B16-3: 空 url raise ValueError（fail-loud）。"""
    with pytest.raises(ValueError, match="url|空"):
        fetch_content("")


def test_fetch_content_accepts_flutter_urls():
    """B16-4: fetch_content 接受各类 Flutter 文档 url（无需 catalog 白名单）。

    flutter-dev 不需要 URL_PATH_TO_CATALOG —— 直接传 url 给 detail()。
    """
    urls = [
        "https://docs.flutter.cn/ui/widgets/layout",
        "https://api.flutter-io.cn/flutter/material/Scaffold-class.html",
        "https://pub.dev/packages/provider",
    ]
    fake_result = {"content": "# 内容", "error": None}
    with patch("scripts.kb.content_fetcher.detail", return_value=fake_result) as mock:
        for url in urls:
            content = fetch_content(url)
            assert content == "# 内容"
    # 每个 url 都应直接传给 detail()
    assert mock.call_count == len(urls)
    for call, expected_url in zip(mock.call_args_list, urls):
        assert call.args[0] == expected_url


def test_default_expire_days_is_30():
    """B16-5: DEFAULT_EXPIRE_DAYS 默认 30 天（与 hap-dev 一致）。"""
    assert DEFAULT_EXPIRE_DAYS == 30
