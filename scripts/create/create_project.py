"""create 子命令：调用 `flutter create` 创建 Flutter 工程。

用法：
    python3 -m scripts.create.create_project --name <name> --out <out_dir>
        [--org <org>] [--platforms android,ios,...]

设计决策：
- 直接调用 Flutter 官方 `flutter create` CLI（成熟工具，无需自定义模板）
- 项目名必须匹配 `^[a-z][a-z0-9_]*$`（Flutter 强制小写蛇形）
- 组织名必须匹配反向域名格式（如 com.example）
- 失败显性化：非零退出码 + stderr 上报（Rule 12）
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from typing import Optional

__all__ = ["create_project", "main"]

# Flutter 项目名规则：小写字母开头 + 小写字母/数字/下划线
APP_NAME_PATTERN = r"^[a-z][a-z0-9_]*$"

# 组织名规则：反向域名（如 com.example、org.flutter.dev）
ORG_PATTERN = r"^[a-z][a-z0-9_]*(\.[a-z][a-z0-9_]*)+$"

# Flutter create 支持的平台集合
PLATFORMS: set[str] = {"android", "ios", "web", "linux", "macos", "windows"}


def create_project(
    name: str,
    out_dir: str,
    platforms: Optional[list[str]] = None,
    org: Optional[str] = None,
) -> dict:
    """调用 `flutter create` 创建工程。

    Args:
        name: 项目名（必须匹配 `^[a-z][a-z0-9_]*$`）
        out_dir: 输出目录路径
        platforms: 平台列表（子集 of PLATFORMS）；None 表示全平台
        org: 组织名（如 com.example）；None 时 flutter 用默认 com.example

    Returns:
        创建结果 dict：{"created", "out_dir", "platforms", "org"}

    Raises:
        ValueError: 项目名/组织名/平台非法时
        RuntimeError: flutter create 非零退出码时
    """
    if not re.match(APP_NAME_PATTERN, name):
        raise ValueError(
            f"项目名必须匹配 {APP_NAME_PATTERN}（Flutter 要求小写字母开头）"
        )
    if org and not re.match(ORG_PATTERN, org):
        raise ValueError(
            f"组织名必须匹配 {ORG_PATTERN}（如 com.example）"
        )
    if platforms:
        invalid = set(platforms) - PLATFORMS
        if invalid:
            raise ValueError(
                f"未知平台: {sorted(invalid)}; 可选: {sorted(PLATFORMS)}"
            )

    cmd = ["flutter", "create", "--project-name", name]
    if org:
        cmd += ["--org", org]
    if platforms:
        cmd += ["--platforms", ",".join(platforms)]
    cmd.append(out_dir)

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    except subprocess.TimeoutExpired as e:
        raise RuntimeError(f"flutter create 超时（{e.timeout}s）") from e
    if result.returncode != 0:
        # Rule 12：失败显性化——抛出 RuntimeError，由调用方处理（不直接 sys.exit，
        # 因为 create_project 是库函数，sys.exit 会杀死宿主进程）
        raise RuntimeError(
            f"flutter create 失败 (exit={result.returncode}):\n{result.stderr}"
        )

    return {
        "created": name,
        "out_dir": out_dir,
        "platforms": platforms or "all",
        "org": org or "com.example",
    }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python3 -m scripts.create.create_project",
        description=(
            "flutter-dev create 子命令：调用 flutter create 创建工程。"
            "支持项目名校验、组织名校验、平台选择。"
        ),
    )
    parser.add_argument(
        "--name", required=True, help="项目名（小写字母开头 + 小写/数字/下划线）"
    )
    parser.add_argument(
        "--out", required=True, help="输出目录路径"
    )
    parser.add_argument(
        "--org",
        default=None,
        help="组织名（反向域名，如 com.example）",
    )
    parser.add_argument(
        "--platforms",
        default=None,
        help="平台列表（逗号分隔，如 android,ios,web）；省略表示全平台",
    )
    return parser


def main(argv: Optional[list[str]] = None) -> int:
    """argparse 入口，返回退出码。"""
    parser = _build_parser()
    try:
        args = parser.parse_args(argv)
    except SystemExit as e:
        return int(e.code) if isinstance(e.code, int) else 2

    platforms: Optional[list[str]] = None
    if args.platforms:
        platforms = [p.strip() for p in args.platforms.split(",") if p.strip()]

    try:
        result = create_project(
            name=args.name,
            out_dir=args.out,
            platforms=platforms,
            org=args.org,
        )
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    except RuntimeError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
