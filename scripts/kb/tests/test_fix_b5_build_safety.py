"""fix-bugs B5: cli._run_build must refuse to build an empty index.

If `parse_all_sidebars` returns `[]` (e.g. all sidebar files are present but
empty, or all lines were category headers with no doc links), `_run_build`
silently builds an empty index. The user gets `{"built": 0, "counts": {}}`
with no error — they only discover the empty DB when queries return nothing.

`build_db.py:152-157` already has the canonical check:

    if not docs:
        raise RuntimeError(
            f"no docs parsed from sidebars_dir={sidebars_dir!r} — "
            "every sidebar produced 0 records; refusing to build an empty index"
        )

`cli._run_build` should reuse the same pattern (Rule 8: don't duplicate; Rule
12: fail loud). The build_db check fires before the embedder/indexer are
touched — the cli check should mirror that ordering.
"""
from __future__ import annotations

import argparse
from types import SimpleNamespace

import pytest

from scripts.kb.cli import _run_build


def _make_args(sidebars_dir: str = "sidebars", config=None) -> argparse.Namespace:
    """Build the Namespace that build_parser produces for `cli build`."""
    return SimpleNamespace(sidebars_dir=sidebars_dir, config=config)


def test_run_build_refuses_empty_sidebars(monkeypatch, tmp_path):
    """B5-1: empty parse result must raise RuntimeError, not silently build empty."""
    # Force parse_all_sidebars to return [] — simulates all sidebars being empty
    # or containing only category headers (no doc links).
    monkeypatch.setattr(
        "scripts.kb.cli.parse_all_sidebars", lambda *_args, **_kw: []
    )

    # _load_cfg reads config.json from cwd; monkeypatch it to return a config
    # so we don't depend on the project's real config.json / data/flutter.qdrant.
    fake_cfg = {
        "embed_model": "test-model",
        "embed_dim": 8,
        "db_path": str(tmp_path / "empty.qdrant"),
        "collection": "test_docs",
        "sidebars_dir": "sidebars",
    }
    monkeypatch.setattr("scripts.kb.cli._load_cfg", lambda _config_arg: fake_cfg)

    args = _make_args(sidebars_dir="sidebars", config=None)
    with pytest.raises(RuntimeError, match="no docs parsed"):
        _run_build(args)


def test_run_build_empty_error_message_mentions_sidebars_dir(monkeypatch, tmp_path):
    """B5-2: the error message must include the sidebars_dir for debuggability."""
    monkeypatch.setattr(
        "scripts.kb.cli.parse_all_sidebars", lambda *_args, **_kw: []
    )
    fake_cfg = {
        "embed_model": "test-model",
        "embed_dim": 8,
        "db_path": str(tmp_path / "empty.qdrant"),
        "collection": "test_docs",
        "sidebars_dir": "sidebars",
    }
    monkeypatch.setattr("scripts.kb.cli._load_cfg", lambda _config_arg: fake_cfg)

    args = _make_args(sidebars_dir="my/custom/path", config=None)
    with pytest.raises(RuntimeError) as excinfo:
        _run_build(args)
    # The error must surface which sidebars_dir produced 0 docs — otherwise
    # the user has to grep the code to find the source of the failure.
    assert "my/custom/path" in str(excinfo.value), (
        f"sidebars_dir missing from error: {excinfo.value!r}"
    )
