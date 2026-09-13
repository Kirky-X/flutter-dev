"""fix-bugs B4: create_project must raise RuntimeError, not sys.exit, on failure.

`create_project` is a library function imported by other Python code. A library
function must NEVER call `sys.exit` — it kills the host process. The current
implementation calls `sys.exit(result.returncode)` on non-zero exit, which:

  - prevents the caller from recovering (the process is gone)
  - violates the docstring contract (it claims to return a dict)
  - makes the function unusable from `main()`'s try/except — sys.exit raises
    SystemExit which is not a normal exception, bypasses `except Exception`,
    and is hard to test (Rule 9: tests shouldn't depend on process death)

Fix: replace `sys.exit(rc)` with `raise RuntimeError(...)`, update the
docstring's Raises section, and extend `main()` to catch RuntimeError and
return a non-zero exit code (preserving CLI behaviour).
"""
from __future__ import annotations

import subprocess

import pytest

from scripts.create.create_project import create_project


def _make_completed(returncode: int, stderr: str = "boom") -> subprocess.CompletedProcess:
    return subprocess.CompletedProcess(
        args=["flutter", "create", "--project-name", "test_app", "/tmp/out"],
        returncode=returncode,
        stdout="",
        stderr=stderr,
    )


def test_create_project_raises_runtime_error_on_nonzero_exit(monkeypatch, tmp_path):
    """B4-1: a non-zero `flutter create` exit must raise RuntimeError, not sys.exit."""
    def fake_run(cmd, *args, **kwargs):
        return _make_completed(returncode=1, stderr="some flutter error")

    monkeypatch.setattr(
        "scripts.create.create_project.subprocess.run", fake_run
    )

    # Must raise RuntimeError (NOT SystemExit) — library functions don't kill
    # the host process.
    with pytest.raises(RuntimeError, match="flutter create 失败"):
        create_project(name="test_app", out_dir=str(tmp_path / "out"))


def test_create_project_runtime_error_includes_exit_code_and_stderr(monkeypatch, tmp_path):
    """B4-2: the RuntimeError message must contain exit code + stderr for debugging."""
    def fake_run(cmd, *args, **kwargs):
        return _make_completed(returncode=42, stderr="pub get failed: ...")

    monkeypatch.setattr(
        "scripts.create.create_project.subprocess.run", fake_run
    )

    with pytest.raises(RuntimeError) as excinfo:
        create_project(name="test_app", out_dir=str(tmp_path / "out"))

    msg = str(excinfo.value)
    assert "42" in msg, f"exit code missing from message: {msg!r}"
    assert "pub get failed" in msg, f"stderr missing from message: {msg!r}"


def test_create_project_does_not_raise_system_exit(monkeypatch, tmp_path):
    """B4-3: explicitly assert it's NOT SystemExit — the old behaviour.

    SystemExit bypasses normal exception handling and is hostile to callers
    embedding create_project. This test guards against regression: if someone
    reintroduces sys.exit, this test fails (SystemExit is not RuntimeError).
    """
    def fake_run(cmd, *args, **kwargs):
        return _make_completed(returncode=1)

    monkeypatch.setattr(
        "scripts.create.create_project.subprocess.run", fake_run
    )

    # pytest.raises(RuntimeError) does NOT catch SystemExit — if sys.exit is
    # used, this test fails with "DID NOT RAISE RuntimeError" (or the process
    # would exit if pytest didn't catch SystemExit).
    with pytest.raises(RuntimeError):
        create_project(name="test_app", out_dir=str(tmp_path / "out"))
