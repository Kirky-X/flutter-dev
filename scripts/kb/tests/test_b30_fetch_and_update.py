"""B30/T-verify: fetch-and-update 一体化增量更新（强制带 context，禁止只写 description）。

验证：
  - 抓取正文后原子写入 context + description + 向量（context 非空）
  - 不传 --description 时从正文自动生成 ≤200 字摘要（跳过目录/噪声片段）
  - 抓到空正文时显式 raise，不写半截数据
"""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from scripts.kb.cli import _auto_summary, main as cli_main
from scripts.kb.tests.conftest import FakeEmbedder, make_doc


def _write_config(tmp_path, db_path, embed_model="test-model-A"):
    cfg = {
        "embed_model": embed_model,
        "embed_dim": 8,
        "embed_source": "",
        "db_path": db_path,
        "collection": "test_docs",
        "sidebars_dir": "sidebars",
        "endpoints": {},
        "query": {"default_top_k": 5},
    }
    p = tmp_path / "config.json"
    p.write_text(json.dumps(cfg, ensure_ascii=False))
    return p


def _build_db(tmp_path, db_path):
    from scripts.kb.indexer import QdrantIndexer

    emb = FakeEmbedder(model_name="test-model-A", dim=8)
    idx = QdrantIndexer(db_path=db_path, collection="test_docs", dim=8)
    doc = make_doc(url="https://docs.flutter.cn/test-doc")
    idx.build([doc], emb)
    idx.close()
    return doc["id"]


def test_fetch_and_update_writes_context_and_description(tmp_path):
    """B30-1: fetch-and-update 原子写入 context（非空）+ 自动摘要 description。"""
    db_path = str(tmp_path / "fa.qdrant")
    cfg_path = _write_config(tmp_path, db_path)
    doc_id = _build_db(tmp_path, db_path)

    fake_content = (
        "# Android Studio\n\n本页目录chevron_right\n\n"
        "在 Android Studio 或 IntelliJ 里开发 Flutter 应用，配置 Dart SDK。"
    )
    captured = {}
    with patch("scripts.kb.cli.fetch_content", return_value=fake_content):
        with patch("scripts.kb.cli.update_content",
                   side_effect=lambda did, ctx, desc, idx, emb: captured.update(
                       doc_id=did, context=ctx, description=desc) or {"updated": did}):
            rc = cli_main([
                "fetch-and-update", "--url", "https://docs.flutter.cn/x",
                "--doc-id", doc_id, "--config", str(cfg_path),
            ])
    out = rc if isinstance(rc, dict) else rc
    assert out["updated"] == doc_id
    # update_content 必须收到非空 context（禁止只写 description）
    assert captured["context"] == fake_content
    assert "目录" not in captured["description"]
    assert len(captured["description"]) <= 200


def test_fetch_and_update_empty_content_raises(tmp_path):
    """B30-2: 抓到空正文时显式 raise，不写半截数据。"""
    db_path = str(tmp_path / "fa2.qdrant")
    cfg_path = _write_config(tmp_path, db_path)
    doc_id = _build_db(tmp_path, db_path)

    with patch("scripts.kb.cli.fetch_content", return_value="   "):
        with pytest.raises(ValueError, match="空正文"):
            cli_main([
                "fetch-and-update", "--url", "https://docs.flutter.cn/x",
                "--doc-id", doc_id, "--config", str(cfg_path),
            ])


def test_auto_summary_skips_noise():
    """B30-3: _auto_summary 跳过目录/噪声片段，返回首个有意义句子。"""
    content = (
        "# Title\n\n本页目录chevron_right\n\n"
        "list\n\n"
        "在 Android Studio 里开发 Flutter 应用，配置 Dart SDK 与设备调试。"
    )
    summary = _auto_summary(content, fallback="https://fallback")
    assert "目录" not in summary
    assert "list" != summary
    assert "Android Studio" in summary


def test_auto_summary_fallback_when_only_noise():
    """B30-4: 正文全是噪声时用 fallback（url）。"""
    content = "本页目录chevron_right\n\nlist\n\n- item\n\n>"
    summary = _auto_summary(content, fallback="https://fallback-url")
    assert summary == "https://fallback-url"
