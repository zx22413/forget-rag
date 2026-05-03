"""Smoke tests for the LangChain adapter.

Lightweight: just verify the import path resolves, the class subclasses
BaseRetriever, and a single round-trip via invoke() returns Documents.
Comprehensive tests live in test_adapter_langchain.py (Tue work).
"""

from __future__ import annotations

import pytest

# Skip the whole module if langchain-core isn't available — the adapter
# is optional, and CI runs both with and without the extra installed.
# E402 is intentional: importorskip must run before the package imports,
# otherwise collection fails when the extra isn't present.
langchain_core = pytest.importorskip("langchain_core")

from forget_rag import ForgettingMemory  # noqa: E402
from forget_rag.adapters import ForgettingRetriever  # noqa: E402


def test_lazy_import_resolves() -> None:
    """from forget_rag.adapters import ForgettingRetriever works."""
    assert ForgettingRetriever is not None


def test_subclasses_base_retriever() -> None:
    from langchain_core.retrievers import BaseRetriever

    assert issubclass(ForgettingRetriever, BaseRetriever)


def test_invoke_round_trip_returns_documents() -> None:
    from langchain_core.documents import Document

    memory = ForgettingMemory(sqlite_path=":memory:")
    try:
        memory.add("the quick brown fox")
        retriever = ForgettingRetriever(memory=memory, k=3)

        docs = retriever.invoke("fox")
        assert len(docs) == 1
        assert isinstance(docs[0], Document)
        assert "fox" in docs[0].page_content
        # Metadata surface the user will rely on
        assert "heat" in docs[0].metadata
        assert "tier" in docs[0].metadata
    finally:
        memory.close()


def test_missing_extra_yields_helpful_import_error(monkeypatch) -> None:
    """If langchain-core isn't installed, the lazy import raises a
    clear pip-install hint instead of a bare ModuleNotFoundError."""
    import sys

    # Simulate langchain_core being unavailable.
    monkeypatch.setitem(sys.modules, "langchain_core", None)
    monkeypatch.setitem(sys.modules, "langchain_core.retrievers", None)

    # Force a re-import of the adapter module so the simulated absence
    # actually triggers the ImportError path.
    sys.modules.pop("forget_rag.adapters.langchain", None)

    import forget_rag.adapters as adapters

    with pytest.raises(ImportError, match=r"forget-rag\[langchain\]"):
        _ = adapters.ForgettingRetriever
