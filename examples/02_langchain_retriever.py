"""
forget-rag x LangChain — minimal retriever example
forget-rag x LangChain — 最小 retriever 範例

Wraps a ForgettingMemory in a LangChain BaseRetriever so it can drop
into any chain that expects a retriever (RAG, agents, RetrievalQA, etc.)

Run / 執行:
    uv sync
    uv run python examples/02_langchain_retriever.py

Requires the [langchain] extra:
    uv pip install 'forget-rag[langchain]'
    # 已在這個 monorepo 的 dev group 預先安裝，直接 uv sync 即可
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from forget_rag import ForgettingMemory
from forget_rag.adapters import ForgettingRetriever


def main() -> None:
    now = datetime.now(UTC)

    memory = ForgettingMemory(sqlite_path=":memory:", decay_halflife_days=30.0)

    # Seed with chunks of mixed ages so heat actually has something to do.
    seed = [
        ("LangChain 0.3 retriever interface uses invoke() not get_relevant_documents().", 0),
        ("LangChain 0.2 retriever uses _get_relevant_documents.", 365),
        ("LangChain 0.1 retriever was very different.", 730),
        ("Use FAISS for in-memory vector search.", 60),
        ("Pinecone offers managed vector hosting.", 90),
    ]
    for text, age_days in seed:
        memory._backend.insert(text=text, now=now - timedelta(days=age_days))

    # Wrap memory in a LangChain BaseRetriever.
    retriever = ForgettingRetriever(memory=memory, k=3)

    # Canonical v0.3 entry point — invoke().
    print("=== Query: 'retriever' ===")
    docs = retriever.invoke("retriever")
    for d in docs:
        heat = d.metadata["heat"]
        tier = d.metadata["tier"]
        print(f"  [{tier}] heat={heat:.3f}  {d.page_content}")

    # In a real chain you would pass `retriever` to RetrievalQA, an agent
    # tool, or any LCEL pipeline — same interface as Chroma/FAISS retrievers.
    # 在真正的 chain 裡，你把 `retriever` 丟給 RetrievalQA、agent tool、
    # 或任何 LCEL pipeline — 介面跟 Chroma / FAISS 的 retriever 一樣。

    memory.close()


if __name__ == "__main__":
    main()
