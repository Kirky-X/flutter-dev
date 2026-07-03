"""fix 子命令 - analyzer 轨道：调用 `dart analyze --format=json` 解析静态分析结果。

用法：
    python3 -m scripts.fix.run_analyzer [project_dir]

流程：
1. 调用 `dart analyze --format=json` 获取机器可读分析结果
2. 解析 JSON 输出，按 severity（error/warning/info）分类
3. 按 error code 路由到 references/error-fixes/analyzer-errors.md
4. 输出结构化 JSON 供 agent 诊断

设计决策：
- analyzer 是 Flutter/Dart 静态分析的标准工具，输出 JSON 格式稳定
- 失败显性化：dart analyze 非零退出码时区分"有错误"vs"工具失败"
  （dart analyze 在发现 error 时返回退出码 1-3，仍会输出有效 JSON）
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Optional

__all__ = ["run_analyzer", "route_error_code", "main"]

# analyzer-errors.md 路由路径（相对于项目根）
ANALYZER_FIX_DOC = "references/error-fixes/analyzer-errors.md"

# dart analyze 退出码语义：
# 0 = 无 issue；1 = 至少一个 error；2 = 至少一个 warning（无 error）；3 = 至少一个 info（无 error/warning）
# 这些退出码表示"分析成功完成但发现 issue"，工具本身的失败（如 SDK 未安装）会导致其他退出码或异常
_ANALYZER_ISSUE_EXIT_CODES = {0, 1, 2, 3}

# severity 等级优先级（用于排序）
_SEVERITY_ORDER = {"error": 3, "warning": 2, "info": 1}

# 已知的高频 analyzer error code → 简短描述（用于 next_action 提示）
# 完整列表见 references/error-fixes/analyzer-errors.md
_ERROR_CODE_HINTS: dict[str, str] = {
    "avoid_print": "库代码中避免使用 print，改用 logger 或 debugPrint",
    "avoid_unnecessary_containers": "Container 无必要时移除，直接使用子 Widget",
    "camel_case_types": "类名应使用 UpperCamelCase",
    "constant_identifier_names": "常量名应使用 lowerCamelCase 或 SCREAMING_CAPS",
    "empty_statements": "删除空语句",
    "file_names": "文件名应使用 snake_case.dart",
    "library_names": "库名应使用 lower_case_with_underscores",
    "non_constant_identifier_names": "非常量标识符应使用 lowerCamelCase",
    "prefer_const_constructors": "可 const 化的构造函数应加 const",
    "prefer_const_declarations": "可用 const 时优先 const 而非 final",
    "prefer_final_fields": "私有字段不可变时加 final",
    "prefer_final_locals": "局部变量不可变时加 final",
    "prefer_single_quotes": "字符串优先使用单引号",
    "require_trailing_commas": "多行集合/参数列表加尾随逗号",
    "sort_child_properties_last": "child 参数应放最后",
    "use_key_in_widget_constructors": "可变 Widget 应接受 Key 参数",
    "unused_import": "删除未使用的 import",
    "unused_local_variable": "删除未使用的局部变量",
    "unnecessary_brace_in_string_interps": "字符串插值无需花括号时移除",
    "unnecessary_const": "重复的 const 移除",
    "unnecessary_new": "Dart 2+ 不需要 new 关键字",
    "unnecessary_null_in_if_null_operators": "移除 ?? null 操作符",
    "use_build_context_synchronously": "异步后使用 BuildContext 需先 mount 检查",
    "use_super_parameters": "优先使用 super 参数",
}


def route_error_code(code: str) -> dict:
    """根据 error code 路由到修复建议。

    Returns:
        {"code", "doc", "hint"} —— doc 指向 references 下的修复文档，
        hint 为简短中文提示（未知 code 时 hint 为空串，让 agent 自行检索）。
    """
    hint = _ERROR_CODE_HINTS.get(code, "")
    return {
        "code": code,
        "doc": ANALYZER_FIX_DOC,
        "hint": hint,
    }


def _classify_severity(issue: dict) -> dict:
    """从单个 analyzer issue 提取关键字段并附加路由建议。"""
    code = issue.get("code", "") or ""
    severity = issue.get("severity", "info") or "info"
    routed = route_error_code(code) if code else {"code": "", "doc": ANALYZER_FIX_DOC, "hint": ""}
    return {
        "severity": severity,
        "code": code,
        "error_message": issue.get("error_message", "") or "",
        "file": issue.get("file", "") or "",
        "line": issue.get("line", 0) or 0,
        "column": issue.get("column", 0) or 0,
        "fix_doc": routed["doc"],
        "hint": routed["hint"],
    }


def run_analyzer(
    project_dir: str = ".",
    dart_bin: str = "dart",
) -> dict:
    """运行 `dart analyze --format=json` 并返回结构化结果。

    Args:
        project_dir: 待分析的工程根目录（含 pubspec.yaml）
        dart_bin: dart 可执行文件名或路径（默认 PATH 中的 dart）

    Returns:
        {
            "project_dir": str,
            "total": int,
            "errors":   list[dict],  # severity == "error"
            "warnings": list[dict],  # severity == "warning"
            "infos":    list[dict],  # severity == "info"
            "fix_doc":  str,         # 全局修复文档路径
            "error":    str | None,  # 工具失败时非空（显性化）
        }

    error 字段非空表示工具调用本身失败（如 dart 未安装、SDK 未配置），
    此时 errors/warnings/infos 仍尽力返回已解析内容（可能为空）。
    """
    cmd = [dart_bin, "analyze", "--format=json"]
    try:
        result = subprocess.run(
            cmd,
            cwd=project_dir,
            capture_output=True,
            text=True,
            timeout=300,
        )
    except FileNotFoundError as exc:
        return {
            "project_dir": project_dir,
            "total": 0,
            "errors": [],
            "warnings": [],
            "infos": [],
            "fix_doc": ANALYZER_FIX_DOC,
            "error": f"dart 可执行文件未找到：{exc}（请确认 Flutter/Dart SDK 已安装并在 PATH）",
        }
    except subprocess.TimeoutExpired as exc:
        return {
            "project_dir": project_dir,
            "total": 0,
            "errors": [],
            "warnings": [],
            "infos": [],
            "fix_doc": ANALYZER_FIX_DOC,
            "error": f"dart analyze 超时（{exc.timeout}s）",
        }

    # dart analyze 在 stdout 输出 JSON；stderr 可能有进度信息
    stdout = result.stdout or ""
    stderr = result.stderr or ""

    # JSON 输出可能包含多行前缀（如 "Analyzing ..."），取最后一个完整 JSON 对象
    parsed: Optional[dict[str, Any]] = None
    try:
        parsed = json.loads(stdout)
    except json.JSONDecodeError:
        # 尝试提取 stdout 中的 JSON 片段
        start = stdout.find("{")
        if start >= 0:
            try:
                parsed = json.loads(stdout[start:])
            except json.JSONDecodeError:
                parsed = None

    # 工具失败：退出码不在已知 issue 退出码集合内 且 无有效 JSON
    if result.returncode not in _ANALYZER_ISSUE_EXIT_CODES and parsed is None:
        return {
            "project_dir": project_dir,
            "total": 0,
            "errors": [],
            "warnings": [],
            "infos": [],
            "fix_doc": ANALYZER_FIX_DOC,
            "error": (
                f"dart analyze 失败 (exit={result.returncode}): "
                f"stdout={stdout[:500]} stderr={stderr[:500]}"
            ),
        }

    if parsed is None:
        # 退出码在已知集合内但 JSON 解析失败——异常情况，显性化
        return {
            "project_dir": project_dir,
            "total": 0,
            "errors": [],
            "warnings": [],
            "infos": [],
            "fix_doc": ANALYZER_FIX_DOC,
            "error": (
                f"dart analyze 退出码 {result.returncode} 但 JSON 解析失败: "
                f"stdout={stdout[:500]}"
            ),
        }

    raw_issues = parsed.get("diagnostics", []) or []
    classified = [_classify_severity(i) for i in raw_issues if isinstance(i, dict)]
    # 按 severity 优先级降序排序
    classified.sort(
        key=lambda x: _SEVERITY_ORDER.get(x["severity"], 0),
        reverse=True,
    )

    errors = [c for c in classified if c["severity"] == "error"]
    warnings = [c for c in classified if c["severity"] == "warning"]
    infos = [c for c in classified if c["severity"] == "info"]

    return {
        "project_dir": project_dir,
        "total": len(classified),
        "errors": errors,
        "warnings": warnings,
        "infos": infos,
        "fix_doc": ANALYZER_FIX_DOC,
        "error": None,
    }


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python3 -m scripts.fix.run_analyzer",
        description=(
            "flutter-dev fix/analyzer：调用 dart analyze --format=json 获取静态分析结果，"
            "按 error code 路由到修复文档。"
        ),
    )
    parser.add_argument(
        "project_dir",
        nargs="?",
        default=".",
        help="待分析的工程根目录（默认当前目录）",
    )
    parser.add_argument(
        "--dart",
        default="dart",
        help="dart 可执行文件路径（默认 PATH 中的 dart）",
    )
    try:
        args = parser.parse_args(argv)
    except SystemExit as e:
        return int(e.code) if isinstance(e.code, int) else 2

    result = run_analyzer(args.project_dir, dart_bin=args.dart)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    # 工具失败时返回非零退出码（与 Rule 12 一致）
    if result["error"]:
        return 1
    # 有 error 级别 issue 时返回 1；warning 返回 2；info 返回 3
    if result["errors"]:
        return 1
    if result["warnings"]:
        return 2
    if result["infos"]:
        return 3
    return 0


# 模块作为脚本直接运行时，需将项目根加入 sys.path 才能正确解析
# `from scripts.fix...` 形式的导入（此处仅 self-contained，无跨模块导入）
if __name__ == "__main__":
    # noqa: 兼容 `python3 scripts/fix/run_analyzer.py` 直接调用
    if __package__ in (None, ""):
        sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    sys.exit(main())
