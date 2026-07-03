"""test 子命令 - 平台检测与 Flutter 测试工具启用策略。

Flutter 是跨平台框架，所有平台都支持 `flutter test`（单元/widget 测试）和
`flutter integration_test`（集成测试）。与 hap-dev 的 HarmonyOS 不同，Flutter
不存在"模拟器工具仅限 Windows/macOS"的限制。

本模块负责：
1. 检测当前操作系统平台
2. 检测 Flutter SDK / Dart SDK 版本
3. 按平台返回启用的测试工具列表（统一支持 flutter test + integration_test）
4. 探测 flutter / dart CLI 是否可调用
5. 生成测试配置 dict
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
from typing import Optional

__all__ = [
    "detect_platform",
    "detect_flutter",
    "enabled_tools",
    "check_flutter_installed",
    "generate_test_config",
    "disabled_tools_hint",
]

# 所有平台都支持的 Flutter 测试工具
# （Flutter 跨平台特性，无 hap-dev 那种平台限制）
_FULL_TOOLS: list[str] = [
    "flutter_test",
    "flutter_integration_test",
    "dart_analyze",
    "flutter_build",
]

# 与 _FULL_TOOLS 相同（语义对称，便于 hap-dev 风格迁移）
_LINUX_TOOLS: list[str] = list(_FULL_TOOLS)

# sys.platform → 内部平台名映射
_PLATFORM_MAP: dict[str, str] = {
    "linux": "linux",
    "win32": "windows",
    "darwin": "macos",
}

# Flutter version 输出正则：`Flutter 3.19.5 • channel stable • ...`
_FLUTTER_VERSION_RE = re.compile(
    r"Flutter\s+(\d+\.\d+(?:\.\d+)?)",
    re.IGNORECASE,
)
# Dart version 输出（独立 dart --version）：`Dart SDK version: 3.3.3 (stable)`
_DART_VERSION_RE = re.compile(
    r"Dart SDK version:\s+(\d+\.\d+(?:\.\d+)?)",
    re.IGNORECASE,
)
# flutter --version 同时输出 Dart 版本：`Dart 3.3.3`
_DART_IN_FLUTTER_RE = re.compile(
    r"Tools • Dart\s+(\d+\.\d+(?:\.\d+)?)",
    re.IGNORECASE,
)


def detect_platform() -> str:
    """检测当前操作系统平台。

    返回 "linux" / "windows" / "macos"。
    未知平台抛 ValueError（Rule 12：失败显性化，不静默退化）。
    """
    plat_name = _PLATFORM_MAP.get(sys.platform)
    if plat_name is None:
        raise ValueError(
            f"不支持的平台 sys.platform={sys.platform!r}，"
            f"仅支持 linux/win32/darwin"
        )
    return plat_name


def _run_version_cmd(cmd: list[str]) -> tuple[int, str, str]:
    """运行版本检测命令，返回 (returncode, stdout, stderr)。"""
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
        return result.returncode, result.stdout, result.stderr
    except (FileNotFoundError, subprocess.SubprocessError, OSError) as exc:
        # 命令不存在——返回 -1 表示工具未安装（Rule 12：显性化）
        return -1, "", str(exc)


def detect_flutter() -> dict:
    """检测 Flutter SDK 和 Dart SDK 版本。

    调用 `flutter --version`（输出同时含 Flutter 和 Dart 版本），
    失败时回退到 `dart --version`。

    Returns:
        {
            "flutter": {"installed": bool, "version": str, "channel": str},
            "dart":    {"installed": bool, "version": str},
            "error":   str | None,
        }

    任一工具未安装时 installed=False 且 error 字段非空（不静默成功）。
    """
    flutter_info: dict = {"installed": False, "version": "", "channel": ""}
    dart_info: dict = {"installed": False, "version": ""}
    errors: list[str] = []

    # 1. flutter --version（同时含 Flutter + Dart 版本）
    rc, stdout, stderr = _run_version_cmd(["flutter", "--version"])
    if rc == 0 and stdout:
        flutter_info["installed"] = True
        m = _FLUTTER_VERSION_RE.search(stdout)
        if m:
            flutter_info["version"] = m.group(1)
        # channel 提取：`• channel stable •`
        ch_match = re.search(r"channel\s+(\w+)", stdout, re.IGNORECASE)
        if ch_match:
            flutter_info["channel"] = ch_match.group(1)
        # Dart 版本（flutter --version 也输出）
        d_match = _DART_IN_FLUTTER_RE.search(stdout)
        if d_match:
            dart_info["installed"] = True
            dart_info["version"] = d_match.group(1)
    elif rc == -1:
        errors.append("flutter CLI 未找到（请确认 Flutter SDK 已安装并在 PATH）")
    else:
        errors.append(f"flutter --version 失败 (exit={rc}): {stderr.strip()[:200]}")

    # 2. 若 flutter --version 未给出 Dart 版本，独立调 dart --version
    if not dart_info["version"]:
        rc2, stdout2, stderr2 = _run_version_cmd(["dart", "--version"])
        if rc2 == 0 and stdout2:
            dart_info["installed"] = True
            m2 = _DART_VERSION_RE.search(stdout2)
            if m2:
                dart_info["version"] = m2.group(1)
            elif stdout2.strip():
                # 容错：直接取首个版本号
                v_match = re.search(r"(\d+\.\d+(?:\.\d+)?)", stdout2)
                if v_match:
                    dart_info["version"] = v_match.group(1)
        elif rc2 == -1:
            errors.append("dart CLI 未找到（请确认 Dart SDK 已安装并在 PATH）")
        else:
            errors.append(f"dart --version 失败 (exit={rc2}): {stderr2.strip()[:200]}")

    return {
        "flutter": flutter_info,
        "dart": dart_info,
        "error": "; ".join(errors) if errors else None,
    }


def enabled_tools(platform: Optional[str] = None) -> list[str]:
    """返回当前平台启用的测试工具列表。

    Flutter 跨平台，所有平台都返回相同的工具集（与 hap-dev 不同）：
    ["flutter_test", "flutter_integration_test", "dart_analyze", "flutter_build"]

    Args:
        platform: 平台名。None 时调用 detect_platform()。

    Raises:
        ValueError: 未知平台时（Rule 12）
    """
    if platform is None:
        platform = detect_platform()
    if platform in ("linux", "windows", "macos"):
        return list(_FULL_TOOLS)
    raise ValueError(
        f"未知平台 {platform!r}，仅支持 linux/windows/macos"
    )


def check_flutter_installed() -> bool:
    """探测 flutter 与 dart CLI 是否可调用。

    策略：shutil.which 检查可执行文件 + flutter --version 验证可运行。
    任何异常返回 False（探针函数，不向上抛，CLI 层会据 result.error 详细提示）。
    """
    if shutil.which("flutter") is None:
        return False
    try:
        result = subprocess.run(
            ["flutter", "--version"],
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
    except (FileNotFoundError, subprocess.SubprocessError, OSError):
        return False
    return result.returncode == 0


def generate_test_config(
    project_path: str,
    coverage: bool = False,
    integration_test_dir: str = "integration_test",
) -> dict:
    """生成 flutter test 测试配置 dict。

    Args:
        project_path: Flutter 工程根路径（含 pubspec.yaml）
        coverage: 是否启用覆盖率收集（--coverage）
        integration_test_dir: 集成测试目录（默认 integration_test/）

    Returns:
        {
            "project_path": str,
            "test_command": ["flutter", "test", ...],
            "integration_command": ["flutter", "test", "integration_test/", ...],
            "coverage": bool,
            "coverage_file": "coverage/lcov.info" | None,
        }
    """
    test_cmd = ["flutter", "test"]
    integration_cmd = ["flutter", "test", integration_test_dir]
    if coverage:
        test_cmd.append("--coverage")
        integration_cmd.append("--coverage")

    return {
        "project_path": project_path,
        "test_command": test_cmd,
        "integration_command": integration_cmd,
        "coverage": coverage,
        "coverage_file": "coverage/lcov.info" if coverage else None,
        "integration_test_dir": integration_test_dir,
    }


def disabled_tools_hint(platform: Optional[str] = None) -> str:
    """返回禁用工具的提示文本。

    Flutter 跨平台，所有平台都支持全部测试工具——故始终返回空串。
    保留此函数是为了与 hap-dev CLI 接口对称（便于复用 cli.py 模板）。
    """
    if platform is None:
        platform = detect_platform()
    if platform in ("linux", "windows", "macos"):
        return ""
    raise ValueError(
        f"未知平台 {platform!r}，仅支持 linux/windows/macos"
    )


def _self_check() -> dict:
    """内部自检：整合平台 + Flutter SDK + Dart SDK 检测结果。

    供 cli.py 的 check 动作调用，输出整合后的 JSON。
    """
    pf = detect_platform()
    tools = enabled_tools(pf)
    sdk = detect_flutter()
    flutter_installed = check_flutter_installed()
    return {
        "platform": pf,
        "enabled_tools": tools,
        "flutter_installed": flutter_installed,
        "flutter_version": sdk["flutter"]["version"],
        "dart_version": sdk["dart"]["version"],
        "channel": sdk["flutter"]["channel"],
        "error": sdk["error"],
    }
