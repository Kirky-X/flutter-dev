"""Flutter documentation page detail fetcher.

Fetches Flutter documentation pages (docs.flutter.cn / api.flutter-io.cn / pub.dev) HTML
content, converts to Markdown and returns.

Usage:
    python3 -m scripts.search.detail <url>

Flow:
1. httpx GET url (follow_redirects=True)
2. html_to_markdown conversion (reuse _http.py)
3. Extract page title (<title> or first <h1>)
4. Return {title, url, content}

Design decisions:
- Does not depend on Flutter-specific APIs (Flutter docs are static HTML sites)
- Error visibility: explicit reporting on HTTP errors / empty content / parsing failures (Rule 12)
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

from urllib.parse import urlparse

from scripts.search._http import (
    COMMON_HEADERS,
    TIMEOUT,
    html_to_markdown,
    http_get,
    DOCS_HOST,
    API_HOST,
    PUB_HOST,
)

__all__ = ["detail", "extract_title", "main"]

# <title>...</title> extraction (DOTALL tolerates multiline)
_TITLE_TAG_RE = re.compile(
    r"<title[^>]*>(.*?)</title>",
    re.DOTALL | re.IGNORECASE,
)
# First <h1>...</h1> extraction (fallback)
_H1_RE = re.compile(
    r"<h1[^>]*>(.*?)</h1>",
    re.DOTALL | re.IGNORECASE,
)
# <meta name="description" content="...">
_META_DESC_RE = re.compile(
    r'<meta\s+name\s*=\s*["\']description["\']\s+content\s*=\s*["\']([^"\']*)["\']',
    re.IGNORECASE,
)
# main / article content containers (prioritize extraction to avoid navigation/sidebar noise)
_MAIN_CONTENT_RE = re.compile(
    r"<(?:main|article)\b[^>]*>(.*?)</(?:main|article)>",
    re.DOTALL | re.IGNORECASE,
)


def _strip_tags(text: str) -> str:
    """Remove HTML tags (for cleaning title text)."""
    return re.sub(r"<[^>]+>", "", text).strip()


def extract_title(html: str) -> str:
    """Extract page title from HTML.

    Priority:
    1. <title> tag content
    2. First <h1> tag content
    3. Empty string

    Removes tags and extra whitespace before returning.
    """
    if not html:
        return ""

    m = _TITLE_TAG_RE.search(html)
    if m:
        title = _strip_tags(m.group(1))
        # Flutter docs <title> often contains " | Flutter" suffix, truncate
        # but keep original if truncated result is empty
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
    """Prioritize extracting content within <main>/<article> to avoid navigation noise.

    If no main/article container exists, return raw HTML (let html_to_markdown process entire content).
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
    """Fetch Flutter documentation page content and convert to Markdown.

    Args:
        url: Documentation URL (e.g., https://docs.flutter.cn/ui/widgets/layout)
        client: Optional httpx.Client (reuse connection pool); None to create new one

    Returns:
        {
            "title": str,
            "url": str,
            "content": str,        # Markdown formatted content
            "description": str,    # <meta description> (may be empty)
            "error": str | None,   # Non-empty on failure (Rule 12)
        }

    When error field is non-empty, content may be empty -- callers should decide next actions based on error.
    """
    if not url or not url.strip():
        raise ValueError("url must not be empty")

    # SSRF protection: limit fetching to official Flutter documentation sites only (prevent intranet/metadata probing, e.g., 169.254.169.254)
    _allowed_hosts = {DOCS_HOST, API_HOST, PUB_HOST}
    _hostname = urlparse(url).hostname
    if _hostname not in _allowed_hosts:
        return {
            "title": "",
            "url": url,
            "content": "",
            "description": "",
            "error": f"blocked: host '{_hostname}' not in allowed {_allowed_hosts} (SSRF 防护)",
        }

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

    # Extract meta description (for description backfill, works with kb module)
    desc_match = _META_DESC_RE.search(text)
    description = desc_match.group(1).strip() if desc_match else ""

    # Prioritize extracting main/article container content to reduce navigation noise
    main_html = _extract_main_content(text)
    markdown = html_to_markdown(main_html)

    if not markdown.strip():
        # Fallback to full content conversion when main content container is empty
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
            "flutter-dev search/detail: Fetch Flutter documentation page content, "
            "convert to Markdown for agent retrieval or description backfill."
        ),
    )
    parser.add_argument(
        "url", help="Documentation URL (e.g., https://docs.flutter.cn/ui/widgets/layout)"
    )
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
    # Return 1 on failure (Rule 12: error visibility)
    if result["error"]:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
