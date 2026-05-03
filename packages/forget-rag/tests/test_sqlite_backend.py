"""Tests for the SQLite + FTS5 backend.

Schema, CRUD, search, namespace isolation, soft-delete semantics.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from forget_rag.backends.sqlite import SqliteBackend

NOW = datetime(2026, 5, 3, 12, 0, 0, tzinfo=UTC)


@pytest.fixture
def backend() -> SqliteBackend:
    return SqliteBackend(":memory:")


# --- schema / lifecycle ---------------------------------------------------


def test_schema_initialises_idempotently() -> None:
    """Re-opening the same DB doesn't blow up on existing objects."""
    with SqliteBackend(":memory:") as b:
        # Just creating it again with the same connection target works
        b._conn.executescript(
            "CREATE TABLE IF NOT EXISTS chunks (id TEXT PRIMARY KEY)"
        )


def test_context_manager_closes_connection() -> None:
    with SqliteBackend(":memory:") as b:
        b.insert("hello")
    # After __exit__, connection is closed; using it should raise.
    import sqlite3

    with pytest.raises(sqlite3.ProgrammingError):
        b.get("anything")


# --- CRUD round-trip ------------------------------------------------------


def test_insert_then_get_returns_same_chunk(backend: SqliteBackend) -> None:
    cid = backend.insert(
        "the quick brown fox",
        tags=["animal", "test"],
        metadata={"source": "demo"},
        now=NOW,
    )
    chunk = backend.get(cid)
    assert chunk is not None
    assert chunk.id == cid
    assert chunk.text == "the quick brown fox"
    assert chunk.tags == ["animal", "test"]
    assert chunk.metadata == {"source": "demo"}
    assert chunk.tier == "L1"
    assert chunk.access_count == 0
    assert chunk.last_access is None
    assert chunk.created_at == NOW
    assert chunk.forgotten_at is None


def test_insert_assigns_uuid_when_none_given(backend: SqliteBackend) -> None:
    cid = backend.insert("foo")
    assert len(cid) == 32  # uuid4 hex


def test_insert_respects_explicit_id(backend: SqliteBackend) -> None:
    cid = backend.insert("foo", chunk_id="my-id")
    assert cid == "my-id"
    assert backend.get("my-id") is not None


def test_get_returns_none_for_missing_id(backend: SqliteBackend) -> None:
    assert backend.get("nope") is None


# --- access tracking ------------------------------------------------------


def test_mark_accessed_increments_count_and_sets_timestamp(
    backend: SqliteBackend,
) -> None:
    cid = backend.insert("foo", now=NOW)
    backend.mark_accessed(cid, now=NOW + timedelta(hours=1))
    backend.mark_accessed(cid, now=NOW + timedelta(hours=2))

    chunk = backend.get(cid)
    assert chunk is not None
    assert chunk.access_count == 2
    assert chunk.last_access == NOW + timedelta(hours=2)


# --- soft delete ----------------------------------------------------------


def test_soft_delete_marks_forgotten_at(backend: SqliteBackend) -> None:
    cid = backend.insert("foo", now=NOW)
    forgot_at = NOW + timedelta(days=1)
    n = backend.soft_delete([cid], now=forgot_at)
    assert n == 1
    chunk = backend.get(cid)
    assert chunk is not None
    assert chunk.forgotten_at == forgot_at


def test_soft_delete_is_idempotent(backend: SqliteBackend) -> None:
    cid = backend.insert("foo")
    assert backend.soft_delete([cid]) == 1
    # Already forgotten — second call affects 0 rows.
    assert backend.soft_delete([cid]) == 0


def test_soft_delete_with_empty_list_is_zero(backend: SqliteBackend) -> None:
    assert backend.soft_delete([]) == 0


def test_iter_alive_excludes_forgotten(backend: SqliteBackend) -> None:
    a = backend.insert("alive")
    b = backend.insert("dead")
    backend.soft_delete([b])
    alive_ids = [c.id for c in backend.iter_alive()]
    assert alive_ids == [a]


# --- search ---------------------------------------------------------------


def test_fts_search_finds_inserted_text(backend: SqliteBackend) -> None:
    backend.insert("the quick brown fox jumps", tags=["animal"])
    backend.insert("a slow green turtle walks", tags=["animal"])
    backend.insert("python programming language", tags=["tech"])

    results = backend.fts_search("fox")
    assert len(results) == 1
    chunk, rel = results[0]
    assert "fox" in chunk.text
    assert rel > 0  # positive relevance per backend contract


def test_fts_search_excludes_forgotten(backend: SqliteBackend) -> None:
    cid = backend.insert("the quick brown fox")
    backend.soft_delete([cid])
    assert backend.fts_search("fox") == []


def test_fts_search_ranks_better_match_higher(backend: SqliteBackend) -> None:
    backend.insert("python python python")
    backend.insert("python is a language")
    results = backend.fts_search("python")
    assert len(results) == 2
    # First result has more matches -> higher relevance
    assert results[0][1] >= results[1][1]


def test_fts_search_returns_empty_for_no_matches(backend: SqliteBackend) -> None:
    backend.insert("hello world")
    assert backend.fts_search("nonexistent_term_xyz") == []


def test_fts_search_respects_limit(backend: SqliteBackend) -> None:
    for i in range(10):
        backend.insert(f"python sample {i}")
    results = backend.fts_search("python", limit=3)
    assert len(results) == 3


# --- tier ----------------------------------------------------------------


def test_set_tier_updates_chunk(backend: SqliteBackend) -> None:
    cid = backend.insert("foo")
    backend.set_tier(cid, "L2")
    chunk = backend.get(cid)
    assert chunk is not None
    assert chunk.tier == "L2"


# --- namespace isolation --------------------------------------------------


def test_namespace_isolates_reads_and_writes() -> None:
    db_path = ":memory:"
    # In-memory DBs are per-connection in sqlite3, so use a shared file
    # would be needed for cross-instance tests. Instead test that
    # namespace filter is honored within one DB by inserting via two
    # backends sharing the same connection... simpler: use two namespaces
    # on the same in-memory backend by switching the attribute.
    a = SqliteBackend(db_path, namespace="alpha")
    a.insert("alpha-only")

    b = SqliteBackend(db_path, namespace="beta")
    # Different in-memory DB — beta sees nothing from alpha (separate conn).
    assert list(b.iter_alive()) == []

    a.close()
    b.close()


def test_namespace_filter_within_same_db(tmp_path) -> None:
    """Two backends on the same on-disk DB but different namespaces are isolated."""
    db_file = tmp_path / "test.db"
    a = SqliteBackend(db_file, namespace="alpha")
    b = SqliteBackend(db_file, namespace="beta")

    a.insert("hello from alpha")
    b.insert("hello from beta")

    alpha_texts = [c.text for c in a.iter_alive()]
    beta_texts = [c.text for c in b.iter_alive()]

    assert alpha_texts == ["hello from alpha"]
    assert beta_texts == ["hello from beta"]

    # Search is also namespace-scoped.
    assert len(a.fts_search("hello")) == 1
    assert len(b.fts_search("hello")) == 1

    a.close()
    b.close()


# --- counts --------------------------------------------------------------


def test_count_alive_tracks_inserts_and_deletes(backend: SqliteBackend) -> None:
    assert backend.count_alive() == 0
    a = backend.insert("a")
    backend.insert("b")
    assert backend.count_alive() == 2
    backend.soft_delete([a])
    assert backend.count_alive() == 1
