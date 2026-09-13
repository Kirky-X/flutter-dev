"""fix-bugs B3: create_project must wrap subprocess.run with a timeout.

Without a timeout, `flutter create` can hang indefinitely (network down, pub
hangs waiting on input, etc.) and the user has no feedback. The sibling module
`run_analyzer.py` already uses timeout=300 + catches TimeoutExpired — this
establishes the project's convention for subprocess calls (Rule 11: follow
existing patterns).

This test monkeypatches `subprocess.run` to raise `TimeoutExpired` and asserts
create_project converts it into a `RuntimeError` matching "超时".
"""
from __future__ import annotations

import subprocess

import pytest

from scripts.create.create_project import create_project


def test_create_project_translates_timeout_to_runtime_error(monkeypatch, tmp_path):
    """B3-1: a hung `flutter create` must surface as RuntimeError("超时...")."""
    cmd_captured: list[list[str]] = []

    def fake_run(cmd, *args, **kwargs):
        cmd_captured.append(cmd)
        # The real subprocess.run requires either timeout or it would block.
        # Assert the production code passes timeout=300 (Rule 5: deterministic
        # value, not a magic number buried in a docstring).
        assert kwargs.get("timeout") == 300, (
            f"create_project must call subprocess.run with timeout=300 "
            f"(matches run_analyzer.py convention); got kwargs={kwargs!r}"
        )
        raise subprocess.TimeoutExpired(cmd=cmd, timeout=300)

    monkeypatch.setattr(
        "scripts.create.create_project.subprocess.run", fake_run
    )

    with pytest.raises(RuntimeError, match="超时"):
        create_project(name="test_app", out_dir=str(tmp_path / "out"))

    # Sanity-check: the patched subprocess.run was actually called.
    assert cmd_captured, "subprocess.run was never invoked"
    assert cmd_captured[0][0] == "flutter"
    assert cmd_captured[0][1] == "create"
