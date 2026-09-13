"""B9: set_payload must reject unknown fields (whitelist enforcement).

原 set_payload 接受任意 fields dict，调用方可写入 'title'/'doc_type' 等字段
绕过 upsert 流程，或写入未知字段污染 payload schema。修复：定义白名单
PAYLOAD_FIELDS，未知字段 fail-loud。
"""
from __future__ import annotations

import pytest

from scripts.kb.indexer import PAYLOAD_FIELDS, QdrantIndexer


def test_payload_fields_whitelist_complete():
    """白名单必须恰好包含 11 个 schema 字段（B14 升级后含 context）。"""
    assert PAYLOAD_FIELDS == frozenset({
        "id", "title", "doc_type", "url", "description",
        "links", "created_at", "updated_at", "content_hash", "embed_model",
        "context",
    })


def test_set_payload_accepts_known_field(indexer, fake_embedder):
    from scripts.kb.tests.conftest import make_doc
    doc = make_doc(url="https://example.com/test-known")
    indexer.upsert(doc, fake_embedder)
    # 不应抛异常
    indexer.set_payload(doc["id"], {"description": "new desc"})


def test_set_payload_rejects_unknown_field(indexer, fake_embedder):
    from scripts.kb.tests.conftest import make_doc
    doc = make_doc(url="https://example.com/test-unknown")
    indexer.upsert(doc, fake_embedder)
    with pytest.raises(ValueError, match="unknown payload field"):
        indexer.set_payload(doc["id"], {"evil_field": "malicious"})


def test_set_payload_rejects_mixed_fields(indexer, fake_embedder):
    from scripts.kb.tests.conftest import make_doc
    doc = make_doc(url="https://example.com/test-mixed")
    indexer.upsert(doc, fake_embedder)
    with pytest.raises(ValueError, match="unknown payload field"):
        indexer.set_payload(doc["id"], {
            "description": "ok",
            "evil_field": "bad",
        })


def test_set_payload_allows_links_and_updated_at(indexer, fake_embedder):
    """links_auto.py 和 links.py 都写 links+updated_at，必须放行。"""
    from scripts.kb.tests.conftest import make_doc
    doc = make_doc(url="https://example.com/test-links")
    indexer.upsert(doc, fake_embedder)
    indexer.set_payload(doc["id"], {
        "links": ["some-other-id"],
        "updated_at": "2026-07-03T00:00:00+00:00",
        "content_hash": "abc123",
    })


def test_set_payload_rejects_empty_fields_dict(indexer, fake_embedder):
    """空 dict 是无意义调用，应显式拒绝（Rule 12: fail loud）。"""
    from scripts.kb.tests.conftest import make_doc
    doc = make_doc(url="https://example.com/test-empty")
    indexer.upsert(doc, fake_embedder)
    with pytest.raises(ValueError, match="no fields to set"):
        indexer.set_payload(doc["id"], {})
