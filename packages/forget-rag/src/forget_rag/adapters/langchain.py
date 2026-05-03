"""LangChain `BaseRetriever` adapter for ForgettingMemory.

Targets `langchain-core >= 0.3`. The async path uses BaseRetriever's
default executor fallback in v0.1 — no real async I/O yet. Override
`_aget_relevant_documents` later when a vector backend with native
async lands.
"""

from __future__ import annotations

from langchain_core.callbacks import CallbackManagerForRetrieverRun
from langchain_core.documents import Document
from langchain_core.retrievers import BaseRetriever
from pydantic import ConfigDict

from forget_rag.memory import ForgettingMemory


class ForgettingRetriever(BaseRetriever):
    """LangChain retriever backed by a `ForgettingMemory`.

    Example:
        >>> from forget_rag import ForgettingMemory
        >>> from forget_rag.adapters import ForgettingRetriever
        >>> memory = ForgettingMemory(sqlite_path=":memory:")
        >>> memory.add("hello world")
        >>> retriever = ForgettingRetriever(memory=memory, k=5)
        >>> docs = retriever.invoke("hello")  # canonical entry point in v0.3
        >>> docs[0].metadata["heat"]  # heat exposed for downstream rerankers

    The `memory` field is `arbitrary_types_allowed` because
    `ForgettingMemory` is not a Pydantic model — it owns a SQLite
    connection and other non-serialisable state.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    memory: ForgettingMemory
    k: int = 5

    def _get_relevant_documents(
        self,
        query: str,
        *,
        run_manager: CallbackManagerForRetrieverRun,
    ) -> list[Document]:
        chunks = self.memory.search(query, limit=self.k)
        return [
            Document(
                page_content=c.text,
                metadata={
                    "id": c.id,
                    "tags": list(c.tags),
                    "tier": c.tier,
                    "heat": c.heat,
                    "score": c.score,
                },
            )
            for c in chunks
        ]
