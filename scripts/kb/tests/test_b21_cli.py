"""B21: CLI 新子命令 fetch-content/update-content/migrate-context/refresh-expired (Red phase).

flutter-dev 适配：不包含 recommend-api 子命令（hap-dev 特有的华为推荐 API）。
保留 4 个 context 相关子命令的端到端测试。
"""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from scripts.kb.cli import main as cli_main
from scripts.kb.tests.conftest import FakeEmbedder, make_doc


def _write_config(tmp_path: Path, db_path: str, embed_model: str = "test-model-A") -> Path:
    cfg = {
        "embed_model": embed_model,
        "embed_dim": 8,
        "embed_source": "",
        "embed_base_url": "",
        "embed_api_key": "",
        "rerank_model": "",
        "rerank_source": "",
        "rerank_base_url": "",
        "rerank_api_key": "",
        "db_path": db_path,
        "collection": "test_docs",
        "sidebars_dir": "sidebars",
        "endpoints": {},
        "query": {"default_top_k": 5, "bm25_weight": 0.3, "vector_weight": 0.7},
    }
    cfg_path = tmp_path / "config.json"
    cfg_path.write_text(json.dumps(cfg, ensure_ascii=False, indent=2))
    return cfg_path


def _build_db_with_doc(db_path: str, url: str = "https://docs.flutter.cn/test-doc") -> str:
    """Build a minimal DB with one doc, return its doc_id."""
    from scripts.kb.indexer import QdrantIndexer
    emb = FakeEmbedder(model_name="test-model-A", dim=8)
    idx = QdrantIndexer(db_path=db_path, collection="test_docs", dim=8)
    doc = make_doc(url=url)
    idx.build([doc], emb)
    idx.close()
    return doc["id"]


# ---------- fetch-content ----------

def test_cli_fetch_content_outputs_content(tmp_path):
    """B21-1: cli fetch-content --url URL 调用 content_fetcher.fetch_content 输出内容。"""
    db_path = str(tmp_path / "fc.qdrant")
    cfg_path = _write_config(tmp_path, db_path)

    fake_content = "# 抓取到的内容\n\n正文。"
    # cli.py 用 `from .content_fetcher import fetch_content` 导入，patch 目标是 cli 模块
    with patch("scripts.kb.cli.fetch_content", return_value=fake_content):
        result = cli_main(["fetch-content", "--url",
                           "https://docs.flutter.cn/ui/widgets/layout",
                           "--config", str(cfg_path)])

    assert result == {"content": fake_content}


# ---------- update-content ----------

def test_cli_update_content_with_context_file(tmp_path):
    """B21-2: cli update-content --doc-id ID --description DESC --context-file FILE。

    context 优先级：--context-file > stdin，两者都无时 raise ValueError。
    """
    db_path = str(tmp_path / "uc.qdrant")
    cfg_path = _write_config(tmp_path, db_path)
    doc_id = _build_db_with_doc(db_path)

    context_file = tmp_path / "ctx.md"
    context_file.write_text("# 网页原始内容", encoding="utf-8")

    # update_content 会触发 indexer.upsert → embedder.embed，用 FakeEmbedder 替换
    fake_emb = FakeEmbedder(model_name="test-model-A", dim=8)
    with patch("scripts.kb.cli.make_embedder", return_value=fake_emb):
        result = cli_main([
            "update-content", "--doc-id", doc_id,
            "--description", "新描述",
            "--context-file", str(context_file),
            "--config", str(cfg_path),
        ])
    assert result == {"updated": doc_id}

    # 验证 DB 中 doc 已更新
    from scripts.kb.indexer import QdrantIndexer
    idx = QdrantIndexer(db_path=db_path, collection="test_docs", dim=8)
    try:
        stored = idx.get(doc_id)
        assert stored["context"] == "# 网页原始内容"
        assert stored["description"] == "新描述"
    finally:
        idx.close()


def test_cli_update_content_no_context_raises(tmp_path, monkeypatch):
    """B21-3: update-content 无 --context-file 且无 stdin → raise ValueError。"""
    db_path = str(tmp_path / "uc-no-ctx.qdrant")
    cfg_path = _write_config(tmp_path, db_path)
    doc_id = _build_db_with_doc(db_path)

    # 模拟空 stdin（无输入）
    monkeypatch.setattr("sys.stdin", _FakeStdin(""))

    with pytest.raises(ValueError, match="context"):
        cli_main([
            "update-content", "--doc-id", doc_id,
            "--description", "新描述",
            "--config", str(cfg_path),
        ])


def test_cli_update_content_from_stdin(tmp_path, monkeypatch):
    """B21-4: update-content 无 --context-file 时从 stdin 读 context。"""
    db_path = str(tmp_path / "uc-stdin.qdrant")
    cfg_path = _write_config(tmp_path, db_path)
    doc_id = _build_db_with_doc(db_path)

    fake_stdin_content = "# 从 stdin 来的内容"
    monkeypatch.setattr("sys.stdin", _FakeStdin(fake_stdin_content))

    # update_content 会触发 indexer.upsert → embedder.embed，用 FakeEmbedder 替换
    fake_emb = FakeEmbedder(model_name="test-model-A", dim=8)
    with patch("scripts.kb.cli.make_embedder", return_value=fake_emb):
        result = cli_main([
            "update-content", "--doc-id", doc_id,
            "--description", "新描述",
            "--config", str(cfg_path),
        ])
    assert result == {"updated": doc_id}

    from scripts.kb.indexer import QdrantIndexer
    idx = QdrantIndexer(db_path=db_path, collection="test_docs", dim=8)
    try:
        stored = idx.get(doc_id)
        assert stored["context"] == fake_stdin_content
    finally:
        idx.close()


class _FakeStdin:
    """模拟 sys.stdin，提供 .read() 方法。"""
    def __init__(self, content: str):
        self._content = content
    def read(self) -> str:
        return self._content
    def strip(self) -> str:
        return self._content.strip()


# ---------- migrate-context ----------

def test_cli_migrate_context_backfills_empty_field(tmp_path):
    """B21-5: migrate-context 给缺 context 字段的 doc 写 ""。"""
    db_path = str(tmp_path / "mc.qdrant")
    cfg_path = _write_config(tmp_path, db_path)
    doc_id = _build_db_with_doc(db_path)

    # 删除 context 字段（模拟 pre-B14 legacy doc——字段不存在）
    # _build_db_with_doc 用新 indexer 写了 context=""，必须 delete_payload 才能真正删除
    from qdrant_client import QdrantClient
    client = QdrantClient(path=db_path)
    pid = int(doc_id[:16], 16)
    client.delete_payload(
        collection_name="test_docs",
        keys=["context"],
        points=[pid],
    )
    client.close()

    result = cli_main(["migrate-context", "--config", str(cfg_path)])
    assert result["migrated"] >= 1
    assert "model" not in result  # migrate-context 不涉及 model


def test_cli_migrate_context_idempotent(tmp_path):
    """B21-6: 已有 context 字段的 doc 不重复迁移。"""
    db_path = str(tmp_path / "mc-idem.qdrant")
    cfg_path = _write_config(tmp_path, db_path)
    _build_db_with_doc(db_path)

    # 第一次迁移
    result1 = cli_main(["migrate-context", "--config", str(cfg_path)])
    # 第二次迁移（幂等）
    result2 = cli_main(["migrate-context", "--config", str(cfg_path)])

    # 第二次应报告 0 个需要迁移（所有 doc 已有 context 字段）
    assert result2["migrated"] == 0


# ---------- refresh-expired ----------

def test_cli_refresh_expired_outputs_doc_id_list(tmp_path):
    """B21-7: refresh-expired --expire-days 30 扫描过期 doc 仅输出 doc_id 列表（不刷新）。"""
    db_path = str(tmp_path / "re.qdrant")
    cfg_path = _write_config(tmp_path, db_path)
    doc_id = _build_db_with_doc(db_path)

    # 手动把 updated_at 设为 31 天前（过期）
    from datetime import datetime, timedelta, timezone
    old_ts = (datetime.now(timezone.utc) - timedelta(days=31)).isoformat()
    from scripts.kb.indexer import QdrantIndexer
    idx = QdrantIndexer(db_path=db_path, collection="test_docs", dim=8)
    idx.set_payload(doc_id, {"updated_at": old_ts})
    idx.close()

    result = cli_main(["refresh-expired", "--expire-days", "30",
                       "--config", str(cfg_path)])

    assert "expired_doc_ids" in result
    assert isinstance(result["expired_doc_ids"], list)
    assert doc_id in result["expired_doc_ids"]
    # 不应刷新——只输出列表
    idx = QdrantIndexer(db_path=db_path, collection="test_docs", dim=8)
    try:
        stored = idx.get(doc_id)
        assert stored["updated_at"] == old_ts, "refresh-expired 不应改 updated_at"
    finally:
        idx.close()


def test_cli_refresh_expired_no_expired_docs(tmp_path):
    """B21-8: 无过期 doc 时返回空列表。"""
    db_path = str(tmp_path / "re-empty.qdrant")
    cfg_path = _write_config(tmp_path, db_path)
    _build_db_with_doc(db_path)  # updated_at 是 now，未过期

    result = cli_main(["refresh-expired", "--expire-days", "30",
                       "--config", str(cfg_path)])
    assert result["expired_doc_ids"] == []


def test_cli_config_merges_defaults_for_legacy_config(tmp_path):
    """B21-9: 旧 config.json 缺 content_expire_days 时，_load_cfg 合并默认值 30。"""
    db_path = str(tmp_path / "legacy-cfg.qdrant")
    # 故意写一个缺 content_expire_days 的旧 config
    cfg = {
        "embed_model": "test-model-A",
        "embed_dim": 8,
        "db_path": db_path,
        "collection": "test_docs",
    }
    cfg_path = tmp_path / "config.json"
    cfg_path.write_text(json.dumps(cfg, ensure_ascii=False, indent=2))

    # 用 config 子命令查看合并后的配置
    result = cli_main(["config", "--config", str(cfg_path)])
    assert result["content_expire_days"] == 30, (
        "旧 config.json 缺 content_expire_days 时应合并默认值 30"
    )
