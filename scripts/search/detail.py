"""Flutter 文档页面详情抓取。

抓取 Flutter 文档页面（docs.flutter.cn / api.flutter-io.cn / pub.dev）的 HTML
内容，转换为 Markdown 后返回。

用法：
    python3 -m scripts.search.detail <url>

流程：
1. httpx GET url（follow_redirects=True）
2. html_to_markdown 转换（复用 _http.py）
3. 提取页面标题（<title> 或第一个 <h1>）
4. 返回 {title, url, content}

设计决策：
- 不依赖 Flutter 专属 API（Flutter 文档是静态 HTML 站点）
- 失败显性化：HTTP 错误 / 空内容 / 解析失败时显式上报（Rule 12）
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Optional

# Allow both ``python3 -m scripts.search.detail`` and direct
# ``python3 scripts/search/detail.py`` invocation by ensuring the project
# root (flutter-dev) is on sys.path when run as a plain script.
if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import httpx

from scripts.search._http import (
    COMMON_HEADERS,
    TIMEOUT,
    html_to_markdown,
    http_get,
)

__all__ = ["detail", "extract_title", "main"]

# <title>...</title> 提取（DOTALL 容忍多行）
_TITLE_TAG_RE = re.compile(
    r"<title[^>]*>(.*?)</title>",
    re.DOTALL | re.IGNORECASE,
)
# 第一个 <h1>...</h1> 提取（fallback）
_H1_RE = re.compile(
    r"<h1[^>]*>(.*?)</h1>",
    re.DOTALL | re.IGNORECASE,
)
# <meta name="description" content="...">
_META_DESC_RE = re.compile(
    r'<meta\s+name\s*=\s*["\']description["\']\s+content\s*=\s*["\']([^"\']*)["\']',
    re.IGNORECASE,
)
# main / article 内容容器（优先提取，避免导航/侧边栏噪声）
_MAIN_CONTENT_RE = re.compile(
    r"<(?:main|article)\b[^>]*>(.*?)</(?:main|article)>",
    re.DOTALL | re.IGNORECASE,
)


def _strip_tags(text: str) -> str:
    """移除 HTML 标签（用于清洗标题文本）。"""
    return re.sub(r"<[^>]+>", "", text).strip()


def extract_title(html: str) -> str:
    """从 HTML 中提取页面标题。

    优先级：
    1. <title> 标签内容
    2. 第一个 <h1> 标签内容
    3. 空串

    返回前会移除标签和多余空白。
    """
    if not html:
        return ""

    m = _TITLE_TAG_RE.search(html)
    if m:
        title = _strip_tags(m.group(1))
        # Flutter 文档 <title> 常含 " | Flutter 中文文档" 后缀，截断
        # 但保留原值若截断后为空
        for sep in [" | Flutter", " - Flutter", " | Flutter中文文档"]:
            if sep in title:
                head = title.split(sep, 1)[0].strip()
                if head:
                    return head
                break
        return title

    m = _H1_RE.search(html)
    if m:
        return _strip_tags(m.group(1))

    return ""


def _extract_main_content(html: str) -> str:
    """优先提取 <main>/<article> 内的内容，避免导航噪声。

    若无 main/article 容器，返回原始 HTML（让 html_to_markdown 全文处理）。
    """
    if not html:
        return ""
    m = _MAIN_CONTENT_RE.search(html)
    if m:
        return m.group(1)
    return html


def detail(
    url: str,
    client: httpx.Client | None = None,
) -> dict:
    """抓取 Flutter 文档页面内容并转换为 Markdown。

    Args:
        url: 文档 URL（如 https://docs.flutter.cn/ui/widgets/layout）
        client: 可选的 httpx.Client（复用连接池）；None 时新建

    Returns:
        {
            "title": str,
            "url": str,
            "content": str,        # Markdown 格式内容
            "description": str,    # <meta description>（可能为空）
            "error": str | None,   # 失败时非空（Rule 12）
        }

    error 字段非空时 content 可能为空——调用方应据 error 决定后续动作。
    """
    if not url or not url.strip():
        raise ValueError("url must not be empty")

    text, err = http_get(url, client=client)
    if err:
        return {
            "title": "",
            "url": url,
            "content": "",
            "description": "",
            "error": err,
        }

    if not text or not text.strip():
        return {
            "title": "",
            "url": url,
            "content": "",
            "description": "",
            "error": f"empty response body from {url}",
        }

    title = extract_title(text)

    # 提取 meta description（用于 description 回填，与 kb 模块配合）
    desc_match = _META_DESC_RE.search(text)
    description = desc_match.group(1).strip() if desc_match else ""

    # 优先提取 main/article 容器内容，减少导航噪声
    main_html = _extract_main_content(text)
    markdown = html_to_markdown(main_html)

    if not markdown.strip():
        # 主内容容器为空时回退到全文转换
        markdown = html_to_markdown(text)

    return {
        "title": title,
        "url": url,
        "content": markdown,
        "description": description,
        "error": None,
    }


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python3 -m scripts.search.detail",
        description=(
            "flutter-dev search/detail：抓取 Flutter 文档页面内容，"
            "转换为 Markdown 供 agent 检索或 description 回填。"
        ),
    )
    parser.add_argument("url", help="文档 URL（如 https://docs.flutter.cn/ui/widgets/layout）")
    try:
        args = parser.parse_args(argv)
    except SystemExit as e:
        return int(e.code) if isinstance(e.code, int) else 2

    try:
        result = detail(args.url)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    print(json.dumps(result, ensure_ascii=False, indent=2))
    # 失败时返回 1（Rule 12：错误显性化）
    if result["error"]:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
