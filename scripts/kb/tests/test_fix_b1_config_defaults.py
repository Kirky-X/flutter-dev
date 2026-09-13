"""fix-bugs B1: DEFAULT_CONFIG must align with config.json (Red phase).

DEFAULT_CONFIG is the fallback used when config.json is missing (e.g. fresh
clone, or cwd outside the project root). If it points at a stale path like
``data/harmonyos.qdrant`` (leftover from the hap-dev fork), the CLI silently
hits a non-existent DB or the wrong collection — query/build break with
confusing errors instead of a clear "config drift" message.

This test pins DEFAULT_CONFIG's db_path / collection to the values that
match the shipped ``config.json`` (Rule 8: single source of truth — fallback
must agree with the canonical config).
"""
from __future__ import annotations

from scripts.kb.config import DEFAULT_CONFIG


def test_default_config_db_path_matches_flutter_layout():
    """db_path fallback must point at the Flutter DB, not the HarmonyOS one."""
    assert DEFAULT_CONFIG["db_path"] == "data/flutter.qdrant", (
        "DEFAULT_CONFIG['db_path'] must be 'data/flutter.qdrant' to match "
        f"config.json; got {DEFAULT_CONFIG['db_path']!r}"
    )


def test_default_config_collection_matches_flutter_layout():
    """collection fallback must be the Flutter collection name."""
    assert DEFAULT_CONFIG["collection"] == "flutter_docs", (
        "DEFAULT_CONFIG['collection'] must be 'flutter_docs' to match "
        f"config.json; got {DEFAULT_CONFIG['collection']!r}"
    )
