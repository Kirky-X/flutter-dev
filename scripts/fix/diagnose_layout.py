"""fix 子命令 - layout 轨道：诊断 Flutter 布局错误。

用法：
    python3 -m scripts.fix.diagnose_layout --log-file <path>
    python3 -m scripts.fix.diagnose_layout --log-text "<error text>"

支持的 Flutter layout 错误类型：
1. RenderFlex overflow（最常见）—— Row/Column 子节点溢出
2. Unbounded constraints —— ListView/Row/Column 在无界约束中
3. Missing Material ancestor —— Material Widget 缺失（如 Scaffold 外用 ListTile）
4. RenderBox layout exceptions —— 通用 RenderBox 布局异常
5. Incorrect use of ParentDataWidget —— ParentDataWidget 误用

输出：错误类型 + 修复建议 + 路由文档路径
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Optional

__all__ = ["diagnose_layout", "LAYOUT_FIX_DOC", "main"]

# 路由路径（相对于项目根）
LAYOUT_FIX_DOC = "references/flutter-ui/common-mistakes.md"

# 错误类型 → (匹配正则列表, 中文描述, 修复建议)
_LAYOUT_PATTERNS: list[tuple[str, list[re.Pattern[str]], str, str]] = [
    (
        "RenderFlex overflowed",
        [
            re.compile(
                r"RenderFlex\s+overflowed\s+by\s+(\d+)\s*pixels?\s+on\s+the\s+(\w+)",
                re.IGNORECASE,
            ),
            re.compile(
                r"Bottom\s+overflowed\s+by\s+(\d+)\s*pixels?",
                re.IGNORECASE,
            ),
            re.compile(
                r"Right\s+overflowed\s+by\s+(\d+)\s*pixels?",
                re.IGNORECASE,
            ),
        ],
        "RenderFlex 溢出（Row/Column 子节点超出父节点尺寸）",
        "1) 检查 Row/Column 是否在无界约束中（如 ListView/ScrollView 内层 Row 未设 mainAxisSize）；"
        "2) 给溢出方向的子节点包 Expanded/Flexible；"
        "3) 文本类节点加 overflow: TextOverflow.ellipsis + maxLines；"
        "4) 确认 MediaType.of(context) 是否正确（横竖屏切换时尺寸变化）。",
    ),
    (
        "Unbounded constraints",
        [
            re.compile(
                r"RenderFlex\s+children\s+have\s+non-zero\s+flex\s+but\s+incoming\s+(?:width|height)\s+constraints\s+are\s+unbounded",
                re.IGNORECASE,
            ),
            re.compile(
                r"unbounded\s+(?:width|height)\s+constraints",
                re.IGNORECASE,
            ),
            re.compile(
                r"ListView\s+has\s+unbounded\s+(?:height|width)",
                re.IGNORECASE,
            ),
        ],
        "无界约束（Unbounded constraints）",
        "1) ListView/GridView 在 Column/Row 中需包 Expanded 或给定 shrinkWrap: true；"
        "2) Row/Column 的 flex 子节点不能放在无界约束的父节点中；"
        "3) SingleChildScrollView 内的 Column 不要给 Column 设置 mainAxisSize 或 Expanded；"
        "4) 检查 NestedScrollView/CustomScrollView 的 viewport 是否有明确约束。",
    ),
    (
        "No Material widget found",
        [
            re.compile(
                r"No\s+Material\s+widget\s+found",
                re.IGNORECASE,
            ),
            re.compile(
                r"requires\s+a\s+Material\s+(?:widget\s+)?ancestor",
                re.IGNORECASE,
            ),
        ],
        "Missing Material ancestor",
        "1) 在 Scaffold 外层包 MaterialApp 或局部包 Material/Widget；"
        "2) ListTile/TextField/InkWell 等需 Material 祖先；"
        "3) 在 dialog/overlay 中使用 Scaffold 时确认根 Widget 为 MaterialApp；"
        "4) 测试代码中 wrap with MaterialApp + Scaffold。",
    ),
    (
        "RenderBox layout exception",
        [
            re.compile(
                r"RenderBox\s+was\s+not\s+laid\s+out",
                re.IGNORECASE,
            ),
            re.compile(
                r"RenderBox\s+layout\s+(?:exception|error)",
                re.IGNORECASE,
            ),
            re.compile(
                r"has\s+unbounded\s+constraints",
                re.IGNORECASE,
            ),
        ],
        "RenderBox 布局异常",
        "1) 检查 Widget 树中是否有循环约束（A 依赖 B 的尺寸，B 又依赖 A）；"
        "2) 自定义 RenderObject 时确认 performLayout 设置了 size；"
        "3) 确认 Constraints 传递链无断裂；"
        "4) 参考官方文档 RenderObject 的 layout 协议。",
    ),
    (
        "Incorrect use of ParentDataWidget",
        [
            re.compile(
                r"Incorrect\s+use\s+of\s+ParentDataWidget",
                re.IGNORECASE,
            ),
            re.compile(
                r"ParentDataWidget\s+.*\s+used\s+for\s+a\s+child\s+that\s+is\s+not\s+a\s+\w+",
                re.IGNORECASE,
            ),
        ],
        "ParentDataWidget 误用",
        "1) Expanded/Flexible 只能直接放在 Row/Column/Flex 内；"
        "2) Positioned 只能放在 Stack 内；"
        "3) Flexible/Expanded 中间不能有其他 Widget 隔层（如 Builder/StatefulBuilder）；"
        "4) 检查 Widget 嵌套结构是否正确。",
    ),
    (
        "setState() called after dispose",
        [
            re.compile(
                r"setState\(\)\s+called\s+after\s+dispose\(\)",
                re.IGNORECASE,
            ),
            re.compile(
                r"setState\(\)\s+called\s+on\s+a\s+widget\s+that\s+is\s+not\s+mounted",
                re.IGNORECASE,
            ),
        ],
        "State 生命周期错误（setState after dispose）",
        "1) 异步回调中调用 setState 前检查 mounted；"
        "2) 在 dispose() 中取消 Timer/StreamSubscription/Future；"
        "3) 使用 if (!mounted) return; 守卫；"
        "4) 长异步任务改用 Completer + cancel 模式。",
    ),
]


def _extract_overflow_detail(text: str) -> dict:
    """从 RenderFlex overflow 错误中提取溢出像素数和方向。"""
    for pattern in _LAYOUT_PATTERNS[0][1]:
        m = pattern.search(text)
        if m:
            pixels = m.group(1) if m.lastindex and m.lastindex >= 1 else ""
            direction = m.group(2) if m.lastindex and m.lastindex >= 2 else ""
            return {
                "overflow_pixels": pixels,
                "overflow_direction": direction,
            }
    return {}


def diagnose_layout(text: str, source: str = "text") -> dict:
    """诊断 Flutter layout 错误文本，返回错误类型 + 修复建议。

    Args:
        text: 包含 layout 错误的日志文本（通常来自 Flutter run 的 stderr）
        source: 日志来源（"text" / "file"）

    Returns:
        {
            "status": "detected" | "no_layout_error" | "parse_failed",
            "source": str,
            "error_type": str,
            "description": str,
            "fix_suggestion": str,
            "fix_doc": str,           # references/flutter-ui/common-mistakes.md
            "details": dict,          # 错误特有字段（如溢出像素数）
            "next_action": str,
        }
    """
    if not text or not text.strip():
        return {
            "status": "parse_failed",
            "source": source,
            "error_type": "",
            "description": "",
            "fix_suggestion": "",
            "fix_doc": LAYOUT_FIX_DOC,
            "details": {},
            "next_action": "输入日志为空，请提供有效的 Flutter layout 错误日志",
        }

    for error_type, patterns, description, suggestion in _LAYOUT_PATTERNS:
        for pattern in patterns:
            if pattern.search(text):
                details: dict = {}
                if error_type == "RenderFlex overflowed":
                    details = _extract_overflow_detail(text)

                next_action = (
                    f"已识别 layout 错误：{error_type}；"
                    f"参考 {LAYOUT_FIX_DOC} 排查修复"
                )

                return {
                    "status": "detected",
                    "source": source,
                    "error_type": error_type,
                    "description": description,
                    "fix_suggestion": suggestion,
                    "fix_doc": LAYOUT_FIX_DOC,
                    "details": details,
                    "next_action": next_action,
                }

    # 文本存在但未匹配任何已知 layout 错误
    return {
        "status": "no_layout_error",
        "source": source,
        "error_type": "",
        "description": "未匹配已知的 Flutter layout 错误模式",
        "fix_suggestion": "",
        "fix_doc": LAYOUT_FIX_DOC,
        "details": {},
        "next_action": (
            "未识别到已知 layout 错误模式；可手动检查 references/flutter-ui/common-mistakes.md，"
            "或调 run_analyzer 排查静态错误，或调 parse_stack_trace 排查运行时异常"
        ),
    }


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python3 -m scripts.fix.diagnose_layout",
        description=(
            "flutter-dev fix/layout：诊断 Flutter layout 错误"
            "（RenderFlex overflow / unbounded constraints / missing Material 等），"
            "输出错误类型 + 修复建议。"
        ),
    )
    g = parser.add_mutually_exclusive_group(required=True)
    g.add_argument(
        "--log-file",
        help="layout 错误日志文件路径",
    )
    g.add_argument(
        "--log-text",
        help="layout 错误日志文本",
    )
    try:
        args = parser.parse_args(argv)
    except SystemExit as e:
        return int(e.code) if isinstance(e.code, int) else 2

    if args.log_file:
        try:
            text = Path(args.log_file).read_text(encoding="utf-8")
        except OSError as exc:
            print(f"error: 读取日志文件失败：{exc}", file=sys.stderr)
            return 2
        source = "file"
    else:
        text = args.log_text or ""
        source = "text"

    result = diagnose_layout(text, source=source)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    status = result["status"]
    if status == "detected":
        return 0
    if status == "no_layout_error":
        return 1
    return 2


if __name__ == "__main__":
    if __package__ in (None, ""):
        sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    sys.exit(main())
