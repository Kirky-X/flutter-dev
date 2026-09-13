"""fix-bugs B6: query._rerank must raise ImportError when flashrank is missing.

First-Principles + Rule 12 (失败必须显性化): when the user explicitly passes
``rerank=True`` but ``flashrank`` isn't installed, the current implementation
silently returns the un-reranked results with a misleading comment claiming
"the caller can detect rerank didn't happen because results are unchanged".
That is silent degradation — the user asked for rerank, got non-rerank, and
has no signal. The fix: raise ImportError with an actionable message.

Spec R-rerank-fallback-001/002:
- rerank=True  + flashrank missing → raise ImportError(match="flashrank is required")
- rerank=False + flashrank missing → return results normally (don't import flashrank)
"""
from __future__ import annotations

import sys

import pytest

from scripts.kb.query import query
from scripts.kb.tests.conftest import make_doc


def _block_flashrank(monkeypatch) -> None:
    """Make ``from flashrank import RankModel`` raise ImportError.

    Setting ``sys.modules["flashrank"] = None`` causes the import system to
    raise ``ImportError: import of flashrank halted; None in sys.modules`` —
    the same exception _rerank's ``except ImportError`` must catch.
    """
    monkeypatch.setitem(sys.modules, "flashrank", None)
    # Block potential submodules too so ``from flashrank import X`` can't
    # bypass via a partially-populated package.
    monkeypatch.setitem(sys.modules, "flashrank.rerank", None)


def test_query_rerank_true_raises_importerror_when_flashrank_missing(
    indexer, fake_embedder, monkeypatch
):
    """B6-1: rerank=True + flashrank missing → raise ImportError (not silent return)."""
    docs = [make_doc(url="https://example.com/a", title="ArkTS 入门")]
    indexer.build(docs, fake_embedder)
    _block_flashrank(monkeypatch)

    with pytest.raises(ImportError, match="flashrank is required") as excinfo:
        query("ArkTS", indexer, fake_embedder, top_k=1, rerank=True)

    msg = str(excinfo.value)
    assert "pip install flashrank" in msg, (
        f"error must tell user how to install: {msg!r}"
    )
    assert "rerank=False" in msg, (
        f"error must offer rerank=False workaround: {msg!r}"
    )


def test_query_rerank_false_succeeds_when_flashrank_missing(
    indexer, fake_embedder, monkeypatch
):
    """B6-2: rerank=False + flashrank missing → return results normally.

    ``query`` must NOT import flashrank on the rerank=False path, so a missing
    flashrank is invisible to the caller. This guards against accidentally
    moving the import to module top-level.
    """
    docs = [make_doc(url="https://example.com/a", title="ArkTS 入门")]
    indexer.build(docs, fake_embedder)
    _block_flashrank(monkeypatch)

    results = query("ArkTS", indexer, fake_embedder, top_k=1, rerank=False)
    assert len(results) >= 1, "rerank=False must return results without flashrank"


def test_query_rerank_true_importerror_chains_original(monkeypatch, indexer, fake_embedder):
    """B6-3: the raised ImportError must chain the original via ``raise ... from e``.

    Rule 12 + Python ergonomics: chaining preserves the original ImportError
    (which names the missing module) so users can debug dependency trees.
    """
    docs = [make_doc(url="https://example.com/a", title="ArkTS 入门")]
    indexer.build(docs, fake_embedder)
    _block_flashrank(monkeypatch)

    with pytest.raises(ImportError) as excinfo:
        query("ArkTS", indexer, fake_embedder, top_k=1, rerank=True)

    # __cause__ is set by ``raise X from e``; __context__ is set by implicit chaining.
    # We require explicit chaining (from e) so the original missing-module error
    # is preserved on __cause__.
    assert excinfo.value.__cause__ is not None, (
        "ImportError must use `raise ... from e` to chain the original ImportError; "
        f"got __cause__={excinfo.value.__cause__!r}"
    )
