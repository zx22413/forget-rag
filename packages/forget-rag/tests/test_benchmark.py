"""Tests for the benchmark harness.

The harness must be **deterministic from seed** — Thursday's experiment
script depends on this so re-runs produce the same numbers and we can
diff results across commits. Most tests pin a seed and assert structure.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from forget_rag import ForgettingMemory
from forget_rag.benchmark import (
    CorpusChunk,
    MeasurementResult,
    format_results_table,
    make_corpus,
    make_query_set,
    measure,
    populate,
)

NOW = datetime(2026, 5, 3, 12, 0, 0, tzinfo=UTC)


# --- corpus generation ----------------------------------------------------


def test_make_corpus_returns_n_chunks() -> None:
    assert len(make_corpus(100)) == 100
    assert len(make_corpus(1)) == 1


def test_make_corpus_zero_or_negative_rejected() -> None:
    for bad in (0, -1, -100):
        with pytest.raises(ValueError, match="n must be > 0"):
            make_corpus(bad)


def test_make_corpus_is_deterministic_with_same_seed() -> None:
    a = make_corpus(50, seed=123)
    b = make_corpus(50, seed=123)
    assert a == b


def test_make_corpus_differs_with_different_seed() -> None:
    a = make_corpus(50, seed=1)
    b = make_corpus(50, seed=2)
    # Texts differ because verb/noun choice depends on rng.
    assert any(x.text != y.text for x, y in zip(a, b, strict=False))


def test_chunks_have_topic_in_text(seed: int = 42) -> None:
    for chunk in make_corpus(20, seed=seed):
        assert chunk.topic in chunk.text


def test_ages_within_documented_buckets() -> None:
    chunks = make_corpus(500, seed=99)
    for c in chunks:
        assert 0.0 <= c.age_days <= 730.0


def test_topic_distribution_is_round_robin() -> None:
    """Each topic should get roughly n/10 chunks for the 10-topic vocab."""
    chunks = make_corpus(100, seed=42)
    counts: dict[str, int] = {}
    for c in chunks:
        counts[c.topic] = counts.get(c.topic, 0) + 1
    # 10 topics, 100 chunks => 10 each (round-robin assignment).
    assert all(v == 10 for v in counts.values())
    assert len(counts) == 10


# --- populate -------------------------------------------------------------


def test_populate_returns_index_to_id_map() -> None:
    mem = ForgettingMemory(sqlite_path=":memory:")
    try:
        corpus = make_corpus(10, seed=1)
        ids = populate(mem, corpus, now=NOW)
        assert len(ids) == 10
        assert set(ids.keys()) == set(range(10))
        # Every id must be retrievable.
        for cid in ids.values():
            assert mem._backend.get(cid) is not None
    finally:
        mem.close()


def test_populate_back_dates_created_at() -> None:
    mem = ForgettingMemory(sqlite_path=":memory:")
    try:
        corpus = [CorpusChunk(text="t", tags=["x"], age_days=100.0, topic="x")]
        ids = populate(mem, corpus, now=NOW)
        row = mem._backend.get(ids[0])
        assert row is not None
        # created_at should be 100 days before NOW.
        delta_days = (NOW - row.created_at).total_seconds() / 86400.0
        assert 99.5 < delta_days < 100.5
    finally:
        mem.close()


# --- query set ------------------------------------------------------------


def test_make_query_set_deterministic() -> None:
    corpus = make_corpus(100, seed=42)
    fake_ids = {i: f"id-{i}" for i in range(len(corpus))}
    a = make_query_set(corpus, fake_ids, n_queries=20, seed=7)
    b = make_query_set(corpus, fake_ids, n_queries=20, seed=7)
    assert a == b


def test_make_query_set_n_queries_respected() -> None:
    corpus = make_corpus(100)
    ids = {i: f"id-{i}" for i in range(100)}
    qs = make_query_set(corpus, ids, n_queries=37)
    assert len(qs) == 37


def test_query_relevant_ids_are_subset_of_known_ids() -> None:
    corpus = make_corpus(50, seed=42)
    ids = {i: f"id-{i}" for i in range(50)}
    queries = make_query_set(corpus, ids, n_queries=10, seed=3)
    valid = set(ids.values())
    for q in queries:
        assert q.relevant_ids.issubset(valid)
        assert len(q.relevant_ids) >= 1


def test_query_text_is_a_known_topic() -> None:
    from forget_rag.benchmark import _TOPICS

    corpus = make_corpus(50, seed=42)
    ids = {i: f"id-{i}" for i in range(50)}
    queries = make_query_set(corpus, ids, n_queries=20, seed=3)
    for q in queries:
        assert q.text in _TOPICS


def test_n_queries_zero_or_negative_rejected() -> None:
    corpus = make_corpus(10)
    ids = {i: f"id-{i}" for i in range(10)}
    with pytest.raises(ValueError, match="n_queries"):
        make_query_set(corpus, ids, n_queries=0)


# --- measurement ----------------------------------------------------------


def test_measure_returns_correct_shape() -> None:
    mem = ForgettingMemory(sqlite_path=":memory:")
    try:
        corpus = make_corpus(50, seed=42)
        ids = populate(mem, corpus, now=NOW)
        queries = make_query_set(corpus, ids, n_queries=10, seed=7)
        result = measure(mem, queries, config_name="test", n_chunks=50)

        assert isinstance(result, MeasurementResult)
        assert result.config_name == "test"
        assert result.n_chunks == 50
        assert result.n_queries == 10
        assert result.latency_p50_ms >= 0
        assert result.latency_p95_ms >= result.latency_p50_ms
        assert result.latency_mean_ms >= 0
        assert 0.0 <= result.precision_at_1 <= 1.0
        assert 0.0 <= result.precision_at_5 <= 1.0
    finally:
        mem.close()


def test_measure_rejects_empty_queries() -> None:
    mem = ForgettingMemory(sqlite_path=":memory:")
    try:
        with pytest.raises(ValueError, match="non-empty"):
            measure(mem, [], config_name="x", n_chunks=0)
    finally:
        mem.close()


def test_heat_boost_improves_precision_over_pure_bm25() -> None:
    """The whole point of forget-rag — heat should outperform raw BM25."""
    corpus = make_corpus(200, seed=42)

    # Config A: pure BM25 (no heat influence)
    mem_a = ForgettingMemory(sqlite_path=":memory:", heat_boost_weight=0.0)
    ids_a = populate(mem_a, corpus, now=NOW)
    queries = make_query_set(corpus, ids_a, n_queries=30, seed=7)
    result_a = measure(mem_a, queries, config_name="bm25", n_chunks=200)

    # Config B: heat-weighted ranking
    mem_b = ForgettingMemory(sqlite_path=":memory:", heat_boost_weight=1.0)
    ids_b = populate(mem_b, corpus, now=NOW)
    # Re-build queries against B's ids — same corpus, same seed → same
    # "relative ranks" so the relevant set is structurally equivalent.
    queries_b = make_query_set(corpus, ids_b, n_queries=30, seed=7)
    result_b = measure(mem_b, queries_b, config_name="heat", n_chunks=200)

    # Heat should at least match BM25 on this corpus, usually beat it.
    assert result_b.precision_at_5 >= result_a.precision_at_5
    # And on freshness-sensitive Precision@1, heat should win clearly.
    assert result_b.precision_at_1 > result_a.precision_at_1

    mem_a.close()
    mem_b.close()


# --- formatting -----------------------------------------------------------


def test_format_results_table_handles_empty() -> None:
    assert "no results" in format_results_table([])


def test_format_results_table_includes_all_configs() -> None:
    results = [
        MeasurementResult(
            config_name="alpha",
            n_chunks=100,
            n_queries=10,
            latency_p50_ms=1.0,
            latency_p95_ms=2.0,
            latency_mean_ms=1.5,
            precision_at_1=0.5,
            precision_at_5=0.8,
        ),
        MeasurementResult(
            config_name="beta",
            n_chunks=200,
            n_queries=20,
            latency_p50_ms=2.0,
            latency_p95_ms=4.0,
            latency_mean_ms=3.0,
            precision_at_1=0.7,
            precision_at_5=0.9,
        ),
    ]
    table = format_results_table(results)
    assert "alpha" in table
    assert "beta" in table
    assert "P@1" in table
    assert "P@5" in table
