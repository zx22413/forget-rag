"""Tests for ForgettingMemory — the public API surface.

Covers add/search/forget round-trip, heat-aware ranking, and the
promotion side-effect of search.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from forget_rag import Chunk, ForgettingMemory

NOW = datetime(2026, 5, 3, 12, 0, 0, tzinfo=UTC)


@pytest.fixture
def mem() -> ForgettingMemory:
    return ForgettingMemory(sqlite_path=":memory:")


# --- construction --------------------------------------------------------


def test_default_init_uses_sqlite_in_memory_via_explicit_path() -> None:
    m = ForgettingMemory(sqlite_path=":memory:")
    assert m.count() == 0
    m.close()


def test_unsupported_backend_raises() -> None:
    with pytest.raises(NotImplementedError, match="v0.2"):
        ForgettingMemory(backend="langchain", sqlite_path=":memory:")


@pytest.mark.parametrize("bad", [0, -1.0, -100.0])
def test_negative_halflife_rejected(bad: float) -> None:
    with pytest.raises(ValueError, match="decay_halflife_days"):
        ForgettingMemory(sqlite_path=":memory:", decay_halflife_days=bad)


def test_negative_heat_weight_rejected() -> None:
    with pytest.raises(ValueError, match="heat_boost_weight"):
        ForgettingMemory(sqlite_path=":memory:", heat_boost_weight=-0.1)


def test_context_manager_closes(mem: ForgettingMemory) -> None:
    with ForgettingMemory(sqlite_path=":memory:") as m:
        m.add("hello")
    # Backend closed — using it should raise.
    import sqlite3

    with pytest.raises(sqlite3.ProgrammingError):
        m.count()


# --- add -----------------------------------------------------------------


def test_add_returns_id_and_count_increments(mem: ForgettingMemory) -> None:
    cid = mem.add("hello world")
    assert isinstance(cid, str) and len(cid) > 0
    assert mem.count() == 1


def test_add_rejects_empty_text(mem: ForgettingMemory) -> None:
    with pytest.raises(ValueError, match="non-empty"):
        mem.add("")


def test_add_persists_tags_and_metadata(mem: ForgettingMemory) -> None:
    cid = mem.add("hello", tags=["a", "b"], metadata={"k": "v"})
    hits = mem.search("hello", limit=1)
    assert len(hits) == 1
    assert hits[0].id == cid
    assert hits[0].tags == ["a", "b"]


# --- search --------------------------------------------------------------


def test_search_empty_query_returns_empty(mem: ForgettingMemory) -> None:
    mem.add("hello")
    assert mem.search("") == []


def test_search_finds_added_text(mem: ForgettingMemory) -> None:
    mem.add("the quick brown fox", tags=["animal"])
    mem.add("python programming", tags=["tech"])

    hits = mem.search("fox")
    assert len(hits) == 1
    assert "fox" in hits[0].text


def test_search_returns_chunk_dataclass(mem: ForgettingMemory) -> None:
    mem.add("python is fun")
    hits = mem.search("python")
    assert len(hits) == 1
    assert isinstance(hits[0], Chunk)
    assert hits[0].heat > 0
    assert hits[0].score > 0
    assert hits[0].tier == "L1"


def test_search_respects_limit(mem: ForgettingMemory) -> None:
    for i in range(10):
        mem.add(f"python sample {i}")
    assert len(mem.search("python", limit=3)) == 3


def test_search_excludes_forgotten(mem: ForgettingMemory) -> None:
    cid = mem.add("the quick brown fox")
    mem.forget([cid])
    assert mem.search("fox") == []


def test_search_marks_chunks_accessed(mem: ForgettingMemory) -> None:
    """Promotion signal: search bumps access_count for returned chunks."""
    mem.add("python is great")
    # First search — heat from access bonus is 0 (count was 0)
    first = mem.search("python", now=NOW)
    heat_before = first[0].heat

    # Second search — access_count incremented, recent access window open
    second = mem.search("python", now=NOW + timedelta(hours=1))
    heat_after = second[0].heat

    assert heat_after > heat_before, "access bonus should raise heat"


# --- heat-aware ranking --------------------------------------------------


def test_hotter_chunk_outranks_colder_with_equal_relevance() -> None:
    """Two chunks with the same text — the recently-accessed one wins."""
    mem = ForgettingMemory(sqlite_path=":memory:", decay_halflife_days=10.0)
    try:
        # Both chunks contain 'banana'. cold_id is older; hot_id we'll
        # access right before the search.
        cold_id = mem.add("banana")
        hot_id = mem.add("banana")

        # Access the hot one a few times to build access bonus.
        for _ in range(5):
            mem.search("banana", limit=2, now=NOW)
            # mark_accessed runs on both since both match — but we can
            # offset by accessing hot_id directly via the backend hook.
            mem._backend.mark_accessed(hot_id, now=NOW)

        hits = mem.search("banana", limit=2, now=NOW + timedelta(minutes=1))
        assert hits[0].id == hot_id
        assert hits[1].id == cold_id
    finally:
        mem.close()


def test_pure_bm25_when_heat_weight_zero() -> None:
    """heat_boost_weight=0 means heat doesn't affect ordering."""
    mem = ForgettingMemory(sqlite_path=":memory:", heat_boost_weight=0.0)
    try:
        a = mem.add("python python python")  # higher BM25
        b = mem.add("python is one of many")  # lower BM25
        hits = mem.search("python", limit=2, now=NOW)
        assert hits[0].id == a
        assert hits[1].id == b
    finally:
        mem.close()


# --- forget --------------------------------------------------------------


def test_forget_returns_affected_count(mem: ForgettingMemory) -> None:
    a = mem.add("a")
    b = mem.add("b")
    assert mem.forget([a, b]) == 2
    assert mem.count() == 0


def test_forget_empty_list_is_zero(mem: ForgettingMemory) -> None:
    assert mem.forget([]) == 0


def test_forget_unknown_id_is_zero(mem: ForgettingMemory) -> None:
    assert mem.forget(["does-not-exist"]) == 0


def test_forget_is_idempotent(mem: ForgettingMemory) -> None:
    cid = mem.add("foo")
    assert mem.forget([cid]) == 1
    assert mem.forget([cid]) == 0


# --- round-trip ----------------------------------------------------------


def test_full_round_trip(mem: ForgettingMemory) -> None:
    """add -> search -> forget -> search returns nothing."""
    cid = mem.add("the only chunk", tags=["solo"])
    hits = mem.search("only")
    assert len(hits) == 1
    assert hits[0].id == cid

    n = mem.forget([cid])
    assert n == 1

    assert mem.search("only") == []
    assert mem.count() == 0


# --- maintenance & health_check ------------------------------------------


def test_maintenance_assigns_tiers_by_heat() -> None:
    """Recent chunks land in L1, older ones get demoted."""
    mem = ForgettingMemory(
        sqlite_path=":memory:",
        decay_halflife_days=30.0,
        tiers={"L1": 1, "L2": 1, "L3": "unlimited"},
    )
    try:
        # Insert with manual timestamps via the backend so we can fake age.
        from datetime import timedelta as td

        hot_id = mem._backend.insert("hot", now=NOW)
        warm_id = mem._backend.insert("warm", now=NOW - td(days=30))
        cold_id = mem._backend.insert("cold", now=NOW - td(days=365))

        dist = mem.maintenance(now=NOW)
        assert dist == {"L1": 1, "L2": 1, "L3": 1}

        assert mem._backend.get(hot_id).tier == "L1"
        assert mem._backend.get(warm_id).tier == "L2"
        assert mem._backend.get(cold_id).tier == "L3"
    finally:
        mem.close()


def test_maintenance_is_idempotent(mem: ForgettingMemory) -> None:
    mem.add("a")
    mem.add("b")
    first = mem.maintenance(now=NOW)
    second = mem.maintenance(now=NOW)
    assert first == second


def test_health_check_returns_report_with_distribution(mem: ForgettingMemory) -> None:
    for i in range(3):
        mem.add(f"chunk {i}")
    report = mem.health_check(now=NOW)
    assert report.total == 3
    assert sum(report.tier_distribution.values()) == 3


def test_health_check_suggests_forgets_for_very_cold_chunks() -> None:
    """Chunks aged many half-lives drop below the heat floor."""
    from datetime import timedelta as td

    mem = ForgettingMemory(sqlite_path=":memory:", decay_halflife_days=30.0)
    try:
        # 12 half-lives: heat ≈ 1 / 4096 ≈ 0.00024, way below default 0.05.
        old_id = mem._backend.insert("ancient history", now=NOW - td(days=365))
        mem._backend.insert("fresh news", now=NOW)

        report = mem.health_check(now=NOW)
        suggested_ids = [s.id for s in report.suggested_forgets]
        assert old_id in suggested_ids
    finally:
        mem.close()
