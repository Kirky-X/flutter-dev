"""fix-bugs B2: query() must refuse to search a DB with mixed embed_models.

A DB containing vectors from two different embed_models is contaminated: cosine
similarity is meaningless across models (First-Principles fact F1). The existing
`_check_model_compatibility` only checks whether the *current* embedder is in
the DB's model set — it does NOT detect that the DB itself holds >1 model.

`cli._run_migrate_embed_model` already refuses mixed DBs with the message
"mixed embed_models" (cli.py:277-281). query must use the same fail-loud
pattern, otherwise a contaminated DB silently returns cross-model search
results that look plausible but are nonsense.

Constructs two docs stamped with different embed_models via set_payload, then
asserts query() raises RuntimeError matching "mixed embed_models".
"""
from __future__ import annotations

import pytest

from scripts.kb.query import query
from scripts.kb.tests.conftest import FakeEmbedder, make_doc


def test_query_refuses_mixed_embed_model_db(indexer, fake_embedder):
    """B2-1: a DB holding docs with two different embed_models must be refused."""
    # Build two docs with the same embedder (so they share embed_model)
    docs = [
        make_doc(url="https://example.com/a", title="Doc A", embed_model="test-model-A"),
        make_doc(url="https://example.com/b", title="Doc B", embed_model="test-model-A"),
    ]
    indexer.build(docs, fake_embedder)

    # Tamper with one doc's embed_model so the DB now has two distinct models.
    # set_payload is the documented way to mutate payload fields — it accepts
    # embed_model (it's in PAYLOAD_FIELDS).
    indexer.set_payload(docs[1]["id"], {"embed_model": "intruder-model-X"})

    with pytest.raises(RuntimeError, match="mixed embed_models"):
        query("test", indexer, fake_embedder, top_k=5)
