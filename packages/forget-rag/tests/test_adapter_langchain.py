"""Comprehensive tests for ForgettingRetriever.

Covers metadata shape, k parameter, sort order, async parity, the
search side-effect (promotion), and Pydantic validation. Smoke is
in test_adapter_langchain_smoke.py — keep that file small so
collection stays fast even on machines without langchain-core.
"""

from __future__ import annotations

import asyncio

import pytest

pytest.importorskip("langchain_core")

from forget_rag import ForgettingMemory  # noqa: E402
from forget_rag.adapters import ForgettingRetriever  # noqa: E402
from langchain_core.documents import Document  # noqa: E402


@pytest.fixture
def memory() -> ForgettingMemory:
    m = ForgettingMemory(sqlite_path=":memory:")
    yield m
    m.close()


@pytest.fixture
def populated(memory: ForgettingMemory) -> ForgettingMemory:
    memory.add("the quick brown fox jumps", tags=["animal", "demo"])
    memory.add("a slow green turtle walks", tags=["animal"])
    memory.add("python programming language", tags=["tech"])
    memory.add("python is dynamic and fun", tags=["tech", "demo"])
    return memory


# --- metadata shape -------------------------------------------------------


def test_each_document_carries_full_metadata(populated: ForgettingMemory) -> None:
    retriever = ForgettingRetriever(memory=populated, k=2)
    docs = retriever.invoke("python")
    assert len(docs) >= 1
    doc = docs[0]
    assert isinstance(doc, Document)
    # page_content == chunk.text
    assert "python" in doc.page_content.lower()
    # The five fields downstream rerankers depend on
    for key in ("id", "tags", "tier", "heat", "score"):
        assert key in doc.metadata, f"missing metadata field: {key}"


def test_tags_metadata_is_a_list(populated: ForgettingMemory) -> None:
    retriever = ForgettingRetriever(memory=populated, k=4)
    docs = retriever.invoke("python")
    for doc in docs:
        assert isinstance(doc.metadata["tags"], list)


def test_heat_and_score_are_numeric(populated: ForgettingMemory) -> None:
    retriever = ForgettingRetriever(memory=populated, k=2)
    docs = retriever.invoke("python")
    for doc in docs:
        assert isinstance(doc.metadata["heat"], (int, float))
        assert isinstance(doc.metadata["score"], (int, float))
        assert doc.metadata["heat"] >= 0
        assert doc.metadata["score"] >= 0


# --- k parameter ----------------------------------------------------------


def test_k_caps_returned_documents(populated: ForgettingMemory) -> None:
    retriever = ForgettingRetriever(memory=populated, k=1)
    assert len(retriever.invoke("python")) == 1


def test_k_default_is_five(memory: ForgettingMemory) -> None:
    for i in range(10):
        memory.add(f"python sample {i}")
    retriever = ForgettingRetriever(memory=memory)
    docs = retriever.invoke("python")
    assert len(docs) == 5


def test_k_larger_than_corpus_returns_all_matches(populated: ForgettingMemory) -> None:
    retriever = ForgettingRetriever(memory=populated, k=100)
    docs = retriever.invoke("python")
    assert 1 <= len(docs) <= 4


# --- sort order -----------------------------------------------------------


def test_documents_sorted_by_score_descending(populated: ForgettingMemory) -> None:
    retriever = ForgettingRetriever(memory=populated, k=10)
    docs = retriever.invoke("python")
    scores = [d.metadata["score"] for d in docs]
    assert scores == sorted(scores, reverse=True)


# --- empty / edge cases ---------------------------------------------------


def test_empty_query_returns_empty(populated: ForgettingMemory) -> None:
    retriever = ForgettingRetriever(memory=populated)
    assert retriever.invoke("") == []


def test_no_match_returns_empty(populated: ForgettingMemory) -> None:
    retriever = ForgettingRetriever(memory=populated)
    assert retriever.invoke("nonexistent_term_zzz") == []


def test_empty_memory_returns_empty(memory: ForgettingMemory) -> None:
    retriever = ForgettingRetriever(memory=memory)
    assert retriever.invoke("anything") == []


# --- search side effect (promotion) --------------------------------------


def test_invoke_marks_returned_chunks_accessed(populated: ForgettingMemory) -> None:
    """Same promotion semantics as ForgettingMemory.search()."""
    retriever = ForgettingRetriever(memory=populated, k=2)

    docs = retriever.invoke("python")
    returned_ids = {d.metadata["id"] for d in docs}

    # access_count for the returned chunks should be >= 1 after one invoke.
    for cid in returned_ids:
        row = populated._backend.get(cid)
        assert row is not None
        assert row.access_count >= 1
        assert row.last_access is not None


# --- async parity --------------------------------------------------------


def test_ainvoke_returns_same_shape_as_invoke(populated: ForgettingMemory) -> None:
    retriever = ForgettingRetriever(memory=populated, k=2)
    sync_docs = retriever.invoke("python")
    async_docs = asyncio.run(retriever.ainvoke("python"))

    assert len(sync_docs) == len(async_docs)
    # Order should match — both ultimately call _get_relevant_documents
    sync_ids = [d.metadata["id"] for d in sync_docs]
    async_ids = [d.metadata["id"] for d in async_docs]
    assert sync_ids == async_ids


def test_ainvoke_returns_documents() -> None:
    """Async path goes through BaseRetriever's executor fallback."""
    mem = ForgettingMemory(sqlite_path=":memory:")
    try:
        mem.add("hello async world")
        retriever = ForgettingRetriever(memory=mem)
        docs = asyncio.run(retriever.ainvoke("async"))
        assert len(docs) == 1
        assert "async" in docs[0].page_content
    finally:
        mem.close()


# --- Pydantic validation -------------------------------------------------


def test_memory_field_is_required() -> None:
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        ForgettingRetriever()  # type: ignore[call-arg]


def test_k_must_be_int(memory: ForgettingMemory) -> None:
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        ForgettingRetriever(memory=memory, k="not-an-int")  # type: ignore[arg-type]


def test_can_construct_with_only_memory(memory: ForgettingMemory) -> None:
    """k has a sensible default."""
    retriever = ForgettingRetriever(memory=memory)
    assert retriever.k == 5
