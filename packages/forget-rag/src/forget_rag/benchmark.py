"""Synthetic benchmark harness for forget-rag.

Produces a deterministic corpus where multiple chunks share each
"topic" but have different ages. Queries name a topic; the relevant
set is the *freshest* few chunks for that topic. Pure BM25 has no
way to prefer fresh-over-stale (all topic chunks share keywords),
so heat boost should noticeably improve Precision@k.

Three knobs the experiment script (Thursday) tunes:
    1. corpus size (n_chunks)
    2. heat_boost_weight (0 = pure BM25, 1 = heat fully weighted)
    3. whether maintenance() runs before search

This module is pure-Python and only depends on the rest of forget-rag.
No external benchmark frameworks. No numpy. Reproducible from seed.
"""

from __future__ import annotations

import random
import time
from dataclasses import dataclass
from datetime import datetime, timedelta

from forget_rag.memory import ForgettingMemory

# --- public dataclasses ---------------------------------------------------


@dataclass(frozen=True, slots=True)
class CorpusChunk:
    text: str
    tags: list[str]
    age_days: float
    topic: str


@dataclass(frozen=True, slots=True)
class Query:
    text: str
    relevant_ids: frozenset[str]


@dataclass(frozen=True, slots=True)
class MeasurementResult:
    config_name: str
    n_chunks: int
    n_queries: int
    latency_p50_ms: float
    latency_p95_ms: float
    latency_mean_ms: float
    precision_at_1: float
    precision_at_5: float


# --- generators ----------------------------------------------------------

# Small fixed vocab so every chunk has overlapping words for BM25 to
# bite, while topic tokens distinguish search targets.
_TOPICS = (
    "alpha",
    "beta",
    "gamma",
    "delta",
    "epsilon",
    "zeta",
    "eta",
    "theta",
    "iota",
    "kappa",
)
_VERBS = ("explores", "describes", "covers", "documents", "summarizes")
_NOUNS = ("framework", "playbook", "guide", "report", "specification")

# Age buckets. Tuning these changes how skewed the corpus is.
_AGE_BUCKETS = (
    (0.20, 0.0, 7.0),     # 20% fresh: 0-7 days
    (0.30, 8.0, 90.0),    # 30% warm: 8-90 days
    (0.50, 91.0, 730.0),  # 50% cold: 91-730 days
)


def _sample_age(rng: random.Random) -> float:
    r = rng.random()
    cumulative = 0.0
    for weight, lo, hi in _AGE_BUCKETS:
        cumulative += weight
        if r < cumulative:
            return rng.uniform(lo, hi)
    # Floating-point edge — return last bucket max.
    return _AGE_BUCKETS[-1][2]


def make_corpus(n: int, *, seed: int = 42) -> list[CorpusChunk]:
    """Generate `n` chunks deterministically.

    Topics cycle round-robin so each topic gets ~n/10 chunks. Within a
    topic, ages span the full distribution, so each topic has fresh
    *and* stale members — the situation forget-rag is designed for.
    """
    if n <= 0:
        raise ValueError("n must be > 0")
    rng = random.Random(seed)

    chunks: list[CorpusChunk] = []
    for i in range(n):
        topic = _TOPICS[i % len(_TOPICS)]
        verb = rng.choice(_VERBS)
        noun = rng.choice(_NOUNS)
        text = f"Topic {topic} {verb} the {noun} version {i}."
        chunks.append(
            CorpusChunk(
                text=text,
                tags=[topic],
                age_days=_sample_age(rng),
                topic=topic,
            )
        )
    return chunks


def populate(
    memory: ForgettingMemory,
    corpus: list[CorpusChunk],
    *,
    now: datetime,
) -> dict[int, str]:
    """Insert corpus into memory with back-dated created_at timestamps.

    Returns a dict mapping corpus index → chunk_id, used downstream
    by `make_query_set` to compute ground-truth relevance.

    Pokes at memory._backend.insert directly because the public add()
    doesn't expose the `now` parameter (intentionally — production
    callers have no need to back-date). For benchmarking we need it.
    """
    ids: dict[int, str] = {}
    for i, chunk in enumerate(corpus):
        ids[i] = memory._backend.insert(
            text=chunk.text,
            tags=chunk.tags,
            now=now - timedelta(days=chunk.age_days),
        )
    return ids


def make_query_set(
    corpus: list[CorpusChunk],
    chunk_ids: dict[int, str],
    *,
    n_queries: int = 50,
    relevant_freshest: int = 3,
    seed: int = 7,
) -> list[Query]:
    """Build queries with ground truth = the N freshest chunks per topic.

    A query string is just the topic name (BM25 will match any chunk
    tagged with it). Without heat, BM25 can't tell fresh from stale,
    so Precision@k is roughly `relevant_freshest / chunks_per_topic`.
    With heat, it should be much higher.
    """
    if n_queries <= 0:
        raise ValueError("n_queries must be > 0")

    # Group chunks by topic, sort fresh→stale.
    by_topic: dict[str, list[tuple[int, CorpusChunk]]] = {}
    for i, chunk in enumerate(corpus):
        by_topic.setdefault(chunk.topic, []).append((i, chunk))
    for topic in by_topic:
        by_topic[topic].sort(key=lambda x: x[1].age_days)

    rng = random.Random(seed)
    topics = sorted(by_topic.keys())  # sorted for determinism across dict orderings

    queries: list[Query] = []
    for _ in range(n_queries):
        topic = rng.choice(topics)
        fresh = by_topic[topic][:relevant_freshest]
        relevant = frozenset(chunk_ids[i] for i, _ in fresh)
        queries.append(Query(text=topic, relevant_ids=relevant))
    return queries


# --- measurement ---------------------------------------------------------


def measure(
    memory: ForgettingMemory,
    queries: list[Query],
    *,
    config_name: str,
    n_chunks: int,
    k: int = 5,
) -> MeasurementResult:
    """Run every query, collect latency + precision."""
    if not queries:
        raise ValueError("queries must be non-empty")

    latencies_ms: list[float] = []
    hits_at_1 = 0
    hits_at_5 = 0

    for q in queries:
        start = time.perf_counter()
        results = memory.search(q.text, limit=k)
        elapsed_ms = (time.perf_counter() - start) * 1000.0
        latencies_ms.append(elapsed_ms)

        result_ids = [r.id for r in results]
        if result_ids and result_ids[0] in q.relevant_ids:
            hits_at_1 += 1
        if any(rid in q.relevant_ids for rid in result_ids):
            hits_at_5 += 1

    latencies_ms.sort()
    n = len(latencies_ms)
    p50 = latencies_ms[n // 2]
    # max(0, ...) so we never index -1 on degenerate single-query runs.
    p95_idx = max(0, min(n - 1, int(round(n * 0.95)) - 1))
    p95 = latencies_ms[p95_idx]
    mean = sum(latencies_ms) / n

    return MeasurementResult(
        config_name=config_name,
        n_chunks=n_chunks,
        n_queries=len(queries),
        latency_p50_ms=p50,
        latency_p95_ms=p95,
        latency_mean_ms=mean,
        precision_at_1=hits_at_1 / len(queries),
        precision_at_5=hits_at_5 / len(queries),
    )


# --- formatting helpers --------------------------------------------------


def format_results_table(results: list[MeasurementResult]) -> str:
    """Human-readable ASCII table for embedding in markdown."""
    if not results:
        return "(no results)"

    header = (
        f"{'config':<24} {'n_chunks':>8} {'n_q':>5} "
        f"{'p50 ms':>8} {'p95 ms':>8} {'mean ms':>9} "
        f"{'P@1':>6} {'P@5':>6}"
    )
    rule = "-" * len(header)
    lines = [header, rule]
    for r in results:
        lines.append(
            f"{r.config_name:<24} {r.n_chunks:>8} {r.n_queries:>5} "
            f"{r.latency_p50_ms:>8.2f} {r.latency_p95_ms:>8.2f} "
            f"{r.latency_mean_ms:>9.2f} "
            f"{r.precision_at_1:>6.2%} {r.precision_at_5:>6.2%}"
        )
    return "\n".join(lines)
