"""test 子命令 CLI 入口。

用法：
    python3 -m scripts.test.cli check
    python3 -m scripts.test.cli config --project-path <path>
        [--coverage] [--integration-test-dir <dir>]
    python3 -m scripts.test.cli run [--project-path <path>] [--integration]
        [--coverage] [--test-file <path>] [--extra-args <args>]

三动作（与 hap-dev 相同结构，但适配 Flutter）：
- check：检测 Flutter SDK / Dart SDK / 平台（输出 JSON）
- config：生成 flutter test 测试配置 JSON
- run：执行测试计划（直接 subprocess 调 `flutter test`
        或 `flutter test integration_test/`，与 hap-dev 输出"建议 MCP 序列"不同）

设计决策：
- Flutter 跨平台，所有平台都支持 flutter test + integration_test
  （无 hap-dev 那种 Linux 仅静态检查 / Win&macOS 模拟器验证的差异）
- run 动作直接调 flutter CLI（Flutter 工具成熟，不需要 MCP 中间层）
- 失败显性化：flutter test 非零退出码时上报 stderr + 退出码（Rule 12）
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from typing import Optional

from scripts.test.platform import (
    check_flutter_installed,
    detect_platform,
    detect_flutter,
    disabled_tools_hint,
    enabled_tools,
    generate_test_config,
)

__all__ = [
    "cmd_check",
    "cmd_config",
    "build_run_plan",
    "cmd_run",
    "main",
]


# ---------------------------------------------------------------------------
# check 动作
# ---------------------------------------------------------------------------


def cmd_check() -> int:
    """输出平台/可用工具/Flutter SDK 安装状态。"""
    pf = detect_platform()
    tools = enabled_tools(pf)
    sdk = detect_flutter()
    flutter_installed = check_flutter_installed()

    result = {
        "platform": pf,
        "enabled_tools": tools,
        "flutter_installed": flutter_installed,
        "flutter_version": sdk["flutter"]["version"],
        "dart_version": sdk["dart"]["version"],
        "channel": sdk["flutter"]["channel"],
        "error": sdk["error"],
        "disabled_hint": disabled_tools_hint(pf),
    }
    print(json.dumps(result, indent=2, ensure_ascii=False))
    # SDK 未安装时返回非零（Rule 12）
    if sdk["error"]:
        return 1
    return 0


# ---------------------------------------------------------------------------
# config 动作
# ---------------------------------------------------------------------------


def cmd_config(
    project_path: str,
    coverage: bool = False,
    integration_test_dir: str = "integration_test",
) -> int:
    """生成 flutter test 测试配置并输出 JSON。"""
    cfg = generate_test_config(
        project_path,
        coverage=coverage,
        integration_test_dir=integration_test_dir,
    )
    print(json.dumps(cfg, indent=2, ensure_ascii=False))
    return 0


# ---------------------------------------------------------------------------
# run 动作
# ---------------------------------------------------------------------------


def build_run_plan(
    project_path: str,
    integration: bool = False,
    coverage: bool = False,
    test_file: Optional[str] = None,
    extra_args: Optional[list[str]] = None,
) -> dict:
    """构建测试执行计划（不执行，仅生成命令 JSON）。

    Args:
        project_path: Flutter 工程根路径
        integration: True 执行集成测试（flutter test integration_test/），
                     False 执行单元/widget 测试（flutter test）
        coverage: 启用 --coverage
        test_file: 指定测试文件路径（如 test/widget_test.dart）；None 表示运行全部
        extra_args: 额外命令行参数（如 ["--name", "MyTest"]）

    Returns:
        {"platform", "workflow", "command", "cwd", "coverage", "warnings"}
    """
    pf = detect_platform()
    warnings: list[str] = []

    if integration:
        workflow = "integration_test"
        # 集成测试：flutter test integration_test/<file>
        if test_file:
            # 用户指定的测试文件相对 integration_test/
            if not test_file.startswith("integration_test"):
                test_path = f"integration_test/{test_file}"
            else:
                test_path = test_file
        else:
            test_path = "integration_test"
        cmd = ["flutter", "test", test_path]
    else:
        workflow = "unit_widget_test"
        if test_file:
            cmd = ["flutter", "test", test_file]
        else:
            cmd = ["flutter", "test"]

    if coverage:
        cmd.append("--coverage")
    if extra_args:
        cmd.extend(extra_args)

    if not check_flutter_installed():
        warnings.append(
            "flutter CLI 未检测到，请先安装 Flutter SDK 并加入 PATH"
        )

    return {
        "platform": pf,
        "workflow": workflow,
        "command": cmd,
        "cwd": project_path,
        "coverage": coverage,
        "warnings": warnings,
    }


def cmd_run(
    project_path: str,
    integration: bool = False,
    coverage: bool = False,
    test_file: Optional[str] = None,
    extra_args: Optional[list[str]] = None,
    execute: bool = True,
) -> int:
    """执行测试计划。

    Args:
        execute: True 直接 subprocess 调用 flutter test；
                 False 仅输出计划 JSON（dry-run，供 agent 决策后自行调用）
    """
    plan = build_run_plan(
        project_path,
        integration=integration,
        coverage=coverage,
        test_file=test_file,
        extra_args=extra_args,
    )

    if not execute:
        print(json.dumps(plan, indent=2, ensure_ascii=False))
        return 0

    # 执行前打印计划（便于审计）
    print(
        json.dumps(
            {"plan": plan, "executing": True},
            indent=2,
            ensure_ascii=False,
        ),
        file=sys.stderr,
    )

    cmd = plan["command"]
    try:
        result = subprocess.run(cmd, cwd=plan["cwd"])
    except FileNotFoundError as exc:
        print(f"error: flutter CLI 未找到：{exc}", file=sys.stderr)
        return 127
    except subprocess.SubprocessError as exc:
        print(f"error: flutter test 执行失败：{exc}", file=sys.stderr)
        return 1

    # 退出码透传（Rule 12：失败显性化，不吞错）
    if result.returncode != 0:
        print(
            f"flutter test 失败 (exit={result.returncode})",
            file=sys.stderr,
        )
    return result.returncode


# ---------------------------------------------------------------------------
# argparse 入口
# ---------------------------------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python3 -m scripts.test.cli",
        description=(
            "flutter-dev test 子命令：Flutter 测试工具链。"
            "支持 check/config/run 三动作（flutter test + integration_test）。"
        ),
    )
    sub = parser.add_subparsers(dest="action")

    sub.add_parser(
        "check", help="检测 Flutter SDK / Dart SDK / 平台"
    )

    p_config = sub.add_parser("config", help="生成 flutter test 测试配置 JSON")
    p_config.add_argument(
        "--project-path", required=True, help="Flutter 工程根路径"
    )
    p_config.add_argument(
        "--coverage",
        action="store_true",
        help="启用 --coverage（输出 coverage/lcov.info）",
    )
    p_config.add_argument(
        "--integration-test-dir",
        default="integration_test",
        help="集成测试目录（默认 integration_test/）",
    )

    p_run = sub.add_parser("run", help="执行 flutter test 测试")
    p_run.add_argument(
        "--project-path",
        default=".",
        help="Flutter 工程根路径（默认当前目录）",
    )
    p_run.add_argument(
        "--integration",
        action="store_true",
        help="执行集成测试（flutter test integration_test/）",
    )
    p_run.add_argument(
        "--coverage",
        action="store_true",
        help="启用 --coverage",
    )
    p_run.add_argument(
        "--test-file",
        default=None,
        help="指定测试文件路径（如 test/widget_test.dart）",
    )
    p_run.add_argument(
        "--extra-args",
        nargs="*",
        default=None,
        help="额外命令行参数（如 --name MyTest）",
    )
    p_run.add_argument(
        "--dry-run",
        action="store_true",
        help="仅输出计划 JSON，不实际执行测试",
    )

    return parser


def main(argv: Optional[list[str]] = None) -> int:
    """argparse 入口，返回退出码。"""
    parser = _build_parser()

    try:
        args = parser.parse_args(argv)
    except SystemExit as e:
        return int(e.code) if isinstance(e.code, int) else 2

    if not args.action:
        parser.print_help(sys.stderr)
        return 2

    if args.action == "check":
        return cmd_check()
    if args.action == "config":
        return cmd_config(
            args.project_path,
            coverage=args.coverage,
            integration_test_dir=args.integration_test_dir,
        )
    if args.action == "run":
        return cmd_run(
            project_path=args.project_path,
            integration=args.integration,
            coverage=args.coverage,
            test_file=args.test_file,
            extra_args=args.extra_args,
            execute=not args.dry_run,
        )

    parser.print_help(sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
