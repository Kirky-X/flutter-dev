"""fix-bugs B7: _make_content_hash must use field separators to prevent collisions.

First-Principles fact F2: content_hash is the doc's "content fingerprint". The
current implementation concatenates ``title + url + doc_type + description``
with NO separator, so ``("ab","cd",...)`` and ``("a","bcd",...)`` produce the
same hash — a field-boundary collision that violates the uniqueness promise.

Spec R-hash-collision-001/002/003:
- Different field boundaries → different hash (collision eliminated)
- Same input → same hash (stability / determinism)
- links order doesn't affect hash (set semantics, sorted)
- links part still participates in the hash (``|links:`` prefix preserved)
"""
from __future__ import annotations

from scripts.kb.sidebar_parser import _make_content_hash


def test_hash_no_collision_title_url_boundary():
    """B7-1: ("ab","cd") vs ("a","bcd") must produce different hashes.

    This is the canonical collision case: with no separator, both concatenate
    to "abcd". With \\x1f separator, they become "ab\\x1fcd" vs "a\\x1fbcd".
    """
    h1 = _make_content_hash("ab", "cd", "t", "d", [])
    h2 = _make_content_hash("a", "bcd", "t", "d", [])
    assert h1 != h2, (
        "field-boundary collision: ('ab','cd') and ('a','bcd') must differ"
    )


def test_hash_no_collision_multi_boundary():
    """B7-2: multiple boundary cases — covers spec's second acceptance criterion."""
    h1 = _make_content_hash("ab", "cd", "t", "d", [])
    h2 = _make_content_hash("abc", "d", "t", "d", [])
    assert h1 != h2, (
        "field-boundary collision: ('ab','cd') and ('abc','d') must differ"
    )


def test_hash_no_collision_title_doc_type_boundary():
    """B7-3: title/doc_type boundary — ('ab', '', 'cd') vs ('a', '', 'bcd').

    Same collision class, different field pair. Catches implementations that
    only separate title/url but forget the rest.
    """
    h1 = _make_content_hash("ab", "", "cd", "d", [])
    h2 = _make_content_hash("a", "", "bcd", "d", [])
    assert h1 != h2


def test_hash_stable_same_input():
    """B7-4: same input called twice → same hash (determinism).

    content_hash is a fingerprint; non-determinism would break every consumer
    (reindex, merge, update_description).
    """
    h1 = _make_content_hash("title", "url", "docs", "desc", ["link1", "link2"])
    h2 = _make_content_hash("title", "url", "docs", "desc", ["link1", "link2"])
    assert h1 == h2


def test_hash_links_order_invariant():
    """B7-5: links order must not affect hash (set semantics, sorted internally).

    Reuses the B4-3 invariant — must still hold after the separator change.
    """
    h1 = _make_content_hash("T", "U", "D", "Desc", ["a", "b"])
    h2 = _make_content_hash("T", "U", "D", "Desc", ["b", "a"])
    assert h1 == h2


def test_hash_links_participate():
    """B7-6: links part must still affect the hash (|links: prefix preserved).

    Spec R-hash-collision-003: the ``|links:`` format is preserved, so links
    still contribute to the hash. If a regression dropped the links part
    entirely, this test would catch it.
    """
    h_empty = _make_content_hash("T", "U", "D", "Desc", [])
    h_with_link = _make_content_hash("T", "U", "D", "Desc", ["link-x"])
    assert h_empty != h_with_link, "links must participate in the hash"


def test_hash_empty_links_vs_no_links_arg_equivalent():
    """B7-7: links=[] and links=None must produce the same hash.

    The function signature defaults ``links: list[str] | None = None`` and
    converts None to [] internally. Both must hash identically (stability).
    """
    h1 = _make_content_hash("T", "U", "D", "Desc", [])
    h2 = _make_content_hash("T", "U", "D", "Desc", None)
    assert h1 == h2
