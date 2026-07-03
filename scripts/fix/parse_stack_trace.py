"""fix 子命令 - runtime 轨道：解析 Dart stack trace。

用法：
    python3 -m scripts.fix.parse_stack_trace --log-file <path>
    python3 -m scripts.fix.parse_stack_trace --log-text "<stack trace text>"

Dart stack trace 格式（标准）：
    #0  FunctionName (file:///path/to/file.dart:10:15)
    #1  Class.method (package:foo/bar.dart:42:5)
    #2  <asynchronous suspension>
    #3  main (file:///app/main.dart:7:3)

提取字段：
- error_type: 异常类型（如 NoSuchMethodError、TypeError、StateError）
- error_message: 异常消息
- stack: list[{function, file, line, column, package}]
- top_frame: 栈顶帧（最可能的出错位置）
- keywords: 用于检索知识库的关键词

设计决策：
- 与 hap-dev 的 jscrash 解析思路类似，但适配 Dart 的 `#N  Func (file:line:col)` 格式
- 失败显性化：解析不到 stack trace 时返回 status="no_stack_trace"，不静默成功
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Optional

__all__ = ["parse_stack_trace", "extract_error_header", "main"]

# Dart stack frame：`#0  FunctionName (location)`
# location 可能是 `file:///abs/path.dart:LINE:COL` 或 `package:foo/bar.dart:LINE:COL`
# 也可能是 `<asynchronous suspension>` / `(...)` 等特殊帧
_FRAME_RE = re.compile(
    r"^#(?P<idx>\d+)\s+(?P<func>\S.*?)\s+\((?P<loc>[^)]*)\)\s*$"
)

# location 内的 file:line:col 解析（容忍 col 缺失）
_LOC_RE = re.compile(
    r"^(?P<file>.+?):(?P<line>\d+)(?::(?P<col>\d+))?$"
)

# 异常头行：`ExceptionType: message` 或 `ExceptionType` 单独一行
# 也匹配 `Unhandled exception:` 前缀
_EXC_RE = re.compile(
    r"^(?:Unhandled exception:\s*)?(?P<type>[A-Z][A-Za-z0-9_<>,\s]*?(?:Error|Exception))(?::\s*(?P<msg>.*))?$"
)

# package: 前缀提取包名
_PKG_RE = re.compile(r"^package:([^/]+)/")

# 特殊帧（非定位信息）
_SPECIAL_FRAMES = {
    "<asynchronous suspension>",
    "<dart:anonymous closure>",
    "(dart:...)",
}


def extract_error_header(text: str) -> tuple[str, str]:
    """从日志文本中提取异常类型和消息。

    扫描前若干行，匹配第一个形如 `ExceptionType: message` 或
    `Unhandled exception: ExceptionType: message` 的行。

    Returns:
        (error_type, error_message)；未匹配时返回 ("", "")
    """
    if not text:
        return "", ""
    # 异常头通常在前 20 行内
    for line in text.splitlines()[:20]:
        stripped = line.strip()
        if not stripped:
            continue
        m = _EXC_RE.match(stripped)
        if m:
            etype = m.group("type").strip()
            msg = (m.group("msg") or "").strip()
            return etype, msg
    return "", ""


def _parse_location(loc: str) -> dict:
    """解析单个 location 字符串为 {file, line, column, package}。"""
    if not loc or loc in _SPECIAL_FRAMES:
        return {"file": loc or "", "line": 0, "column": 0, "package": ""}

    m = _LOC_RE.match(loc)
    if not m:
        # location 无行号（如 `dart:core`）
        return {"file": loc, "line": 0, "column": 0, "package": _extract_package(loc)}

    file_path = m.group("file")
    line = int(m.group("line"))
    col = int(m.group("col")) if m.group("col") else 0
    return {
        "file": file_path,
        "line": line,
        "column": col,
        "package": _extract_package(file_path),
    }


def _extract_package(file_path: str) -> str:
    """从 `package:foo/bar.dart` 提取包名 `foo`；其他返回空串。"""
    if not file_path:
        return ""
    m = _PKG_RE.match(file_path)
    return m.group(1) if m else ""


def _extract_keywords(error_type: str, error_message: str, top_frame: dict) -> list[str]:
    """提取检索关键词（去重、按优先级排序）。

    关键词用于在 knowledge base 中检索修复建议。
    """
    kws: list[str] = []
    if error_type:
        kws.append(error_type)
    # 从 message 中提取标识符（驼峰/下划线词）
    if error_message:
        # 提取 >= 3 字符的英文标识符片段
        identifiers = re.findall(r"\b[A-Za-z_][A-Za-z0-9_]{2,}\b", error_message)
        kws.extend(identifiers[:3])  # 取前 3 个避免噪声
    if top_frame and top_frame.get("package"):
        kws.append(top_frame["package"])
    # 去重保序
    seen: set[str] = set()
    out: list[str] = []
    for k in kws:
        if k and k not in seen:
            seen.add(k)
            out.append(k)
    return out


def parse_stack_trace(text: str, source: str = "text") -> dict:
    """解析 Dart stack trace 文本，返回结构化诊断结果。

    Args:
        text: 包含异常和 stack trace 的原始日志文本
        source: 日志来源标记（"text" / "file"），仅用于结果记录

    Returns:
        {
            "status": "detected" | "no_stack_trace" | "parse_failed",
            "source": str,
            "error_type": str,
            "error_message": str,
            "stack": list[dict],
            "top_frame": dict | None,
            "suspected_file": str,    # top_frame.file（便于 agent 快速定位）
            "keywords": list[str],
            "next_action": str,
        }

    status 语义：
    - detected: 解析到至少一帧定位信息
    - no_stack_trace: 文本中无 stack frame（可能不是异常日志）
    - parse_failed: 文本为空或异常情况
    """
    if not text or not text.strip():
        return {
            "status": "parse_failed",
            "source": source,
            "error_type": "",
            "error_message": "",
            "stack": [],
            "top_frame": None,
            "suspected_file": "",
            "keywords": [],
            "next_action": "输入日志为空，请提供有效的 Dart 异常日志",
        }

    error_type, error_message = extract_error_header(text)

    # 收集所有 stack frame（按 #N 顺序）
    stack: list[dict] = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        m = _FRAME_RE.match(stripped)
        if not m:
            continue
        idx = int(m.group("idx"))
        func = m.group("func").strip()
        loc = m.group("loc").strip()
        loc_info = _parse_location(loc)
        stack.append(
            {
                "index": idx,
                "function": func,
                "file": loc_info["file"],
                "line": loc_info["line"],
                "column": loc_info["column"],
                "package": loc_info["package"],
                "raw": stripped,
            }
        )

    if not stack:
        # 文本存在但无 stack frame
        return {
            "status": "no_stack_trace",
            "source": source,
            "error_type": error_type,
            "error_message": error_message,
            "stack": [],
            "top_frame": None,
            "suspected_file": "",
            "keywords": _extract_keywords(error_type, error_message, {}),
            "next_action": (
                "未检测到 Dart stack frame（#N Function (file:line:col) 格式），"
                "请确认输入是完整的 Dart 异常日志"
            ),
        }

    top_frame = stack[0]
    keywords = _extract_keywords(error_type, error_message, top_frame)
    suspected_file = top_frame.get("file", "")

    next_action = (
        f"栈顶帧：{top_frame['function']} @ {suspected_file}:{top_frame['line']}；"
        f"参考 references/error-fixes/runtime-errors.md 排查 {error_type or '运行时异常'}"
    )

    return {
        "status": "detected",
        "source": source,
        "error_type": error_type,
        "error_message": error_message,
        "stack": stack,
        "top_frame": top_frame,
        "suspected_file": suspected_file,
        "keywords": keywords,
        "next_action": next_action,
    }


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python3 -m scripts.fix.parse_stack_trace",
        description=(
            "flutter-dev fix/runtime：解析 Dart stack trace，"
            "提取 error type/message/file/line/function 供 agent 诊断。"
        ),
    )
    g = parser.add_mutually_exclusive_group(required=True)
    g.add_argument(
        "--log-file",
        help="异常日志文件路径",
    )
    g.add_argument(
        "--log-text",
        help="异常日志文本（直接传入）",
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

    result = parse_stack_trace(text, source=source)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    # detected=0；no_stack_trace=1（文本有效但非异常日志）；parse_failed=2
    status = result["status"]
    if status == "detected":
        return 0
    if status == "no_stack_trace":
        return 1
    return 2


if __name__ == "__main__":
    if __package__ in (None, ""):
        sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    sys.exit(main())
