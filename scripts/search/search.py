"""Flutter 文档本地 sidebars 关键词匹配搜索。

Flutter 没有统一的搜索 API（不同于 hap-dev 的 Huawei 端点），搜索策略：
1. 本地 sidebars 匹配（主力）：在 sidebars/*.md 中按关键词匹配标题
2. URL 内容抓取（辅助）：见 detail.py，从 docs.flutter.cn 等抓取页面内容

用法：
    python3 -m scripts.search.search <keyword> [--doc-type docs|api|ai-docs]
        [--top-k 10] [--sidebars-dir <path>]

复用 scripts/kb/sidebar_parser.py 的 parse_all_sidebars 加载 sidebars
（Rule 8：不重复实现已有功能）。
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Optional

# Allow both ``python3 -m scripts.search.search`` and direct
# ``python3 scripts/search/search.py`` invocation by ensuring the project
# root (flutter-dev) is on sys.path when run as a plain script.
if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.kb.sidebar_parser import (
    SIDEBAR_FILE_MAP,
    parse_all_sidebars,
    parse_sidebar,
)

__all__ = ["search", "main"]

DEFAULT_TOP_K = 10
MAX_TOP_K = 100
_VALID_DOC_TYPES = set(SIDEBAR_FILE_MAP.values())  # {"docs", "api", "ai-docs"}


def _score_title(keyword: str, title: str) -> int:
    """关键词与标题的匹配分数（确定性打分，Rule 5）。

    打分规则（高优先级在前）：
    - 完全相等：100
    - 标题以 keyword 开头：80
    - 标题包含 keyword（子串）：60
    - 标题包含 keyword 的所有 token（空格切分）：40
    - 标题包含任一 token：20
    - 不匹配：0
    """
    if not keyword or not title:
        return 0
    kw = keyword.lower().strip()
    ti = title.lower().strip()
    if kw == ti:
        return 100
    if ti.startswith(kw):
        return 80
    if kw in ti:
        return 60
    # 多 token 匹配
    tokens = [t for t in kw.split() if t]
    if not tokens:
        return 0
    matched = sum(1 for t in tokens if t in ti)
    if matched == len(tokens):
        return 40
    if matched > 0:
        return 20
    return 0


def search(
    keyword: str,
    doc_type: Optional[str] = None,
    top_k: int = DEFAULT_TOP_K,
    sidebars_dir: Optional[str] = None,
) -> dict:
    """在本地 sidebars 中按关键词匹配文档标题。

    Args:
        keyword: 搜索关键词（如 "ListView" / "RenderFlex"）
        doc_type: 文档类型过滤（"docs" / "api" / "ai-docs"）；None 表示全部
        top_k: 返回前 K 条匹配（默认 10，上限 100）
        sidebars_dir: sidebars 目录路径；None 时默认 <project_root>/sidebars

    Returns:
        {
            "keyword": str,
            "doc_type": str | None,
            "total": int,
            "results": list[{
                "title": str,
                "url": str,
                "doc_type": str,
                "score": int,
            }],
            "errors": list[str],   # 加载失败的 sidebar 文件（Rule 12：显性化）
        }

    Raises:
        ValueError: keyword 为空 / doc_type 非法 / top_k 非法时
    """
    if not keyword or not keyword.strip():
        raise ValueError("keyword must not be empty")
    if top_k <= 0:
        raise ValueError(f"top_k must be > 0, got {top_k}")
    if top_k > MAX_TOP_K:
        raise ValueError(f"top_k must be <= {MAX_TOP_K}, got {top_k}")
    if doc_type is not None and doc_type not in _VALID_DOC_TYPES:
        raise ValueError(
            f"Unknown doc_type: {doc_type!r}; expected one of {sorted(_VALID_DOC_TYPES)}"
        )

    # 默认 sidebars 目录：scripts/search/search.py -> parents[2] = project_root
    if sidebars_dir is None:
        sidebars_dir = str(Path(__file__).resolve().parents[2] / "sidebars")

    # 加载 sidebars（按 doc_type 过滤）
    docs: list[dict] = []
    errors: list[str] = []
    if doc_type is None:
        # 加载所有 sidebars
        try:
            docs = parse_all_sidebars(sidebars_dir)
        except FileNotFoundError as exc:
            errors.append(str(exc))
    else:
        # 仅加载指定 doc_type 对应的 sidebar
        fname = next(
            (f for f, dt in SIDEBAR_FILE_MAP.items() if dt == doc_type),
            None,
        )
        if fname is None:
            # 不会发生（前面已校验 doc_type），但保留防御
            errors.append(f"no sidebar file mapped to doc_type={doc_type!r}")
        else:
            fpath = Path(sidebars_dir) / fname
            if not fpath.exists():
                errors.append(f"missing sidebar: {fpath}")
            else:
                try:
                    docs = parse_sidebar(str(fpath), doc_type)
                except FileNotFoundError as exc:
                    errors.append(str(exc))

    # 关键词匹配 + 打分
    scored: list[dict] = []
    for doc in docs:
        title = doc.get("title", "") or ""
        score = _score_title(keyword, title)
        if score > 0:
            scored.append(
                {
                    "title": title,
                    "url": doc.get("url", "") or "",
                    "doc_type": doc.get("doc_type", "") or "",
                    "score": score,
                }
            )

    # 按 score 降序，同分按 title 字母序（确定性排序，Rule 5）
    scored.sort(key=lambda x: (-x["score"], x["title"]))

    # 截断到 top_k
    top_results = scored[:top_k]

    return {
        "keyword": keyword,
        "doc_type": doc_type,
        "total": len(scored),
        "results": top_results,
        "errors": errors,
    }


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python3 -m scripts.search.search",
        description=(
            "flutter-dev search 子命令：本地 sidebars 关键词匹配。"
            "在 sidebars/*.md 中按标题匹配 Flutter 文档。"
        ),
    )
    parser.add_argument("keyword", help="搜索关键词（如 ListView / RenderFlex）")
    parser.add_argument(
        "--doc-type",
        choices=sorted(_VALID_DOC_TYPES),
        default=None,
        help="文档类型过滤（docs=中文文档 / api=API参考 / ai-docs=AI文档）",
    )
    parser.add_argument(
        "--top-k",
        type=int,
        default=DEFAULT_TOP_K,
        help=f"返回前 K 条匹配（默认 {DEFAULT_TOP_K}，上限 {MAX_TOP_K}）",
    )
    parser.add_argument(
        "--sidebars-dir",
        default=None,
        help="sidebars 目录路径（默认 <project_root>/sidebars）",
    )
    try:
        args = parser.parse_args(argv)
    except SystemExit as e:
        return int(e.code) if isinstance(e.code, int) else 2

    try:
        result = search(
            args.keyword,
            doc_type=args.doc_type,
            top_k=args.top_k,
            sidebars_dir=args.sidebars_dir,
        )
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    print(json.dumps(result, ensure_ascii=False, indent=2))
    # 完全无匹配 + 加载失败时返回 1（Rule 12）
    if result["total"] == 0 and result["errors"] and not result["results"]:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
