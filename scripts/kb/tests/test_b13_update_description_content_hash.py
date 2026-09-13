"""B13: update_description MUST recompute content_hash after changing description.

B4 把 description 加入 content_hash 公式后，update_description 必须同步更新
content_hash 字段。否则：
1. content_hash 字段说"无描述"，实际 description 已回填 → 数据不一致
2. 后续 reindex 看到 content_hash 不匹配 → 无谓重新嵌入（浪费计算）
3. 审计日志读 content_hash 判断"文档是否变过"会得到错误答案
"""
from __future__ import annotations

import pytest

from scripts.kb.sidebar_parser import NO_DESCRIPTION, _make_content_hash
from scripts.kb.update_description import update_description


def test_update_description_recomputes_content_hash(indexer, fake_embedder):
    """update_description 后 content_hash 必须反映新 description。"""
    from scripts.kb.tests.conftest import make_doc
    doc = make_doc(url="https://example.com/test-hash")
    indexer.upsert(doc, fake_embedder)
    original_hash = doc["content_hash"]

    new_desc = "这是一个新的描述，用于测试 content_hash 是否更新"
    updated = update_description(doc["id"], new_desc, indexer, fake_embedder)

    # content_hash 必须变了
    assert updated["content_hash"] != original_hash
    # 且新 content_hash 必须与用新 description 计算的一致
    expected = _make_content_hash(
        doc["title"], doc["url"], doc["doc_type"],
        new_desc, doc.get("links", []),
    )
    assert updated["content_hash"] == expected


def test_update_description_hash_consistent_with_reindex(indexer, fake_embedder):
    """update_description 后，reindex 不应误判为"需要重新嵌入"。

    场景：update_description 改了 description + content_hash + 向量。
    reindex 用 stored doc 的字段重算 content_hash，应与 stored 一致 → 跳过。
    """
    from scripts.kb.tests.conftest import make_doc
    from scripts.kb.reindex import reindex
    doc = make_doc(url="https://example.com/test-reindex")
    indexer.upsert(doc, fake_embedder)

    new_desc = "另一个描述，验证 reindex 不会重复嵌入"
    update_description(doc["id"], new_desc, indexer, fake_embedder)

    # reindex 不应重新嵌入（content_hash 已同步更新）
    n = reindex(indexer, fake_embedder, force=False)
    assert n == 0, f"reindex 误判需要重新嵌入 {n} 个文档（content_hash 应已同步）"


def test_update_description_hash_changes_with_different_desc(indexer, fake_embedder):
    """不同 description 产生不同 content_hash。"""
    from scripts.kb.tests.conftest import make_doc
    doc = make_doc(url="https://example.com/test-diff")
    indexer.upsert(doc, fake_embedder)

    desc1 = "描述一"
    desc2 = "描述二"
    u1 = update_description(doc["id"], desc1, indexer, fake_embedder)
    hash1 = u1["content_hash"]
    u2 = update_description(doc["id"], desc2, indexer, fake_embedder)
    hash2 = u2["content_hash"]
    assert hash1 != hash2
