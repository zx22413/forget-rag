"""
Chroma + forget-rag integration pattern
Chroma + forget-rag 整合 pattern

Two responsibilities, one pipeline:
    Chroma     -- vector recall (semantic similarity).
    forget-rag -- heat-aware re-ranking (freshness / access promotion)
                  + suggesting which chunks are safe to forget.

This example uses a `FakeChroma` (a 5-line dict-based stand-in) so
you can run it without `pip install chromadb`. To swap in real Chroma,
replace `FakeChroma` with a chromadb collection — the surface used
here (`add(ids, documents)`, `query(query_text, n_results)`) matches.

Run / 執行:
    uv sync
    uv run python examples/03_chroma_with_forget_rag.py
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from forget_rag import ForgettingMemory

# --- minimal Chroma stand-in --------------------------------------------
# Pretends to be a vector store. Real Chroma would do cosine similarity
# on embeddings; we do crude word-overlap so the example is self-
# contained and reproducible.


@dataclass
class _FakeQueryResult:
    ids: list[list[str]]
    documents: list[list[str]]
    distances: list[list[float]]


class FakeChroma:
    def __init__(self) -> None:
        self._docs: dict[str, str] = {}

    def add(self, ids: list[str], documents: list[str]) -> None:
        for i, d in zip(ids, documents, strict=True):
            self._docs[i] = d

    def query(self, query_text: str, n_results: int = 10) -> _FakeQueryResult:
        q_words = set(re.findall(r"\w+", query_text.lower()))
        scored = []
        for cid, doc in self._docs.items():
            d_words = set(re.findall(r"\w+", doc.lower()))
            overlap = len(q_words & d_words)
            distance = 1.0 / (1.0 + overlap)  # smaller = better, like cosine
            scored.append((cid, doc, distance))
        scored.sort(key=lambda x: x[2])
        top = scored[:n_results]
        return _FakeQueryResult(
            ids=[[c for c, _, _ in top]],
            documents=[[d for _, d, _ in top]],
            distances=[[s for _, _, s in top]],
        )


# --- the integration pattern -------------------------------------------


def search_hybrid(
    chroma: FakeChroma,
    memory: ForgettingMemory,
    chroma_to_memory_id: dict[str, str],
    query: str,
    *,
    recall_pool: int = 10,
    final_k: int = 5,
    now: datetime | None = None,
) -> list[tuple[str, float, float, float]]:
    """
    Combine Chroma's vector recall with forget-rag's heat scoring.

    Steps:
      1. Chroma returns a wide candidate pool ranked by semantic similarity.
      2. Look up each candidate's heat in forget-rag.
      3. Final rank = (1 - distance) + heat_weight * heat
      4. Return top-k, marking them accessed in forget-rag (promotion).

    Returns list of (text, vector_score, heat, combined) sorted best-first.
    """
    now = now or datetime.now(UTC)
    heat_weight = 1.0

    # 1. Vector recall
    recall = chroma.query(query, n_results=recall_pool)
    chroma_ids = recall.ids[0]
    docs = recall.documents[0]
    distances = recall.distances[0]

    # 2. Pull heat for each candidate from forget-rag.
    ranked = []
    for cid, doc, dist in zip(chroma_ids, docs, distances, strict=True):
        mem_id = chroma_to_memory_id.get(cid)
        if mem_id is None:
            continue
        row = memory._backend.get(mem_id)
        if row is None:
            continue
        # compute heat using forget-rag's helpers
        from forget_rag.heat import HeatInputs, compute_heat

        heat = compute_heat(
            HeatInputs(
                base_score=row.base_score,
                created_at=row.created_at,
                last_access=row.last_access,
                access_count=row.access_count,
            ),
            now=now,
        )
        vector_score = 1.0 - dist  # flip distance → larger = better
        combined = vector_score + heat_weight * heat
        ranked.append((doc, vector_score, heat, combined, mem_id))

    # 3. Sort + promote top-k
    ranked.sort(key=lambda x: x[3], reverse=True)
    top = ranked[:final_k]
    for *_, mem_id in top:
        memory._backend.mark_accessed(mem_id, now=now)

    return [(doc, vs, heat, comb) for doc, vs, heat, comb, _ in top]


def main() -> None:
    now = datetime.now(UTC)

    chroma = FakeChroma()
    memory = ForgettingMemory(sqlite_path=":memory:")

    # Seed both stores with the same texts. Track id mapping.
    seed = [
        ("doc-1", "How to deploy a Python app to AWS Lambda.",            0),
        ("doc-2", "AWS Lambda deployment guide for Python (2025 edition).", 30),
        ("doc-3", "AWS Lambda deployment guide for Python (2022 edition).", 700),
        ("doc-4", "Kubernetes pods and services overview.",               60),
        ("doc-5", "Old Heroku deployment notes — service shut down.",     1200),
    ]

    chroma.add(
        ids=[cid for cid, _, _ in seed],
        documents=[text for _, text, _ in seed],
    )

    chroma_to_memory_id: dict[str, str] = {}
    for cid, text, age_days in seed:
        mem_id = memory._backend.insert(text=text, now=now - timedelta(days=age_days))
        chroma_to_memory_id[cid] = mem_id

    # First, ask forget-rag what's cold. Chroma has no opinion on
    # this — it is exactly the gap forget-rag fills. We do this BEFORE
    # the hybrid search so the access bumps from search don't muddy the
    # report.
    print("=== forget-rag suggestions (pre-search) ===")
    report = memory.health_check(now=now)
    if not report.suggested_forgets:
        print("  (none — try aging more chunks)")
    for s in report.suggested_forgets:
        print(f"  - {s.text!r}  ({s.reason})")

    # Then run the hybrid pipeline.
    print("\n=== Hybrid search: 'AWS Lambda Python deploy' ===\n")
    results = search_hybrid(
        chroma,
        memory,
        chroma_to_memory_id,
        query="AWS Lambda Python deploy",
        now=now,
    )
    for text, vec, heat, combined in results:
        print(f"  vec={vec:.3f}  heat={heat:.3f}  combined={combined:.3f}")
        print(f"    {text}")

    memory.close()


if __name__ == "__main__":
    main()
