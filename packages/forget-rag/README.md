# forget-rag

A forgetting layer for RAG systems — heat-based decay, tiered storage,
and graceful eviction so your knowledge base doesn't get dumber over time.

> **Status:** v0.1 (alpha). BM25 + heat ranking, L1/L2/L3 tiers, soft
> delete with restore-ready schema. Vector layer lands in v0.2.

## Install

```bash
pip install forget-rag

# with the LangChain adapter
pip install "forget-rag[langchain]"
```

## Quickstart

```python
from forget_rag import ForgettingMemory

memory = ForgettingMemory(
    backend="sqlite",
    decay_halflife_days=30,
    tiers={"L1": 1000, "L2": 10000, "L3": "unlimited"},
)

memory.add("Some knowledge chunk", tags=["meeting", "2026-Q1"])
results = memory.search("query", limit=5)   # auto-promotes hot chunks
report = memory.health_check()              # what should be forgotten?
```

## What's in the box

- **Heat score** — every chunk has a decay function based on access
  frequency + recency.
- **L1 / L2 / L3 tiers** — modeled after CPU cache; hot stays in vector
  + FTS, warm in FTS only, cold is archived but searchable.
- **Soft delete** — `forget()` flags rather than drops; v0.2 will expose
  `restore()` on top of the existing `forgotten_at` column.
- **LangChain adapter** — `ForgettingRetriever` extends `BaseRetriever`
  for drop-in chain use.

## Companion CLI

The [`mem-broom`](https://pypi.org/project/mem-broom/) package wraps
this library with a typer-based CLI for ad-hoc memory hygiene.

## Links

- Repo: https://github.com/zx22413/forget-rag
- Benchmark write-up: https://github.com/zx22413/forget-rag/blob/main/docs/benchmark.md
- Architecture: https://github.com/zx22413/forget-rag/blob/main/docs/architecture.md
- Issues: https://github.com/zx22413/forget-rag/issues

## License

MIT.
