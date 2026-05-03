[English](README.md) | [繁體中文](README.zh-TW.md)

# forget-rag

> RAG systems get dumber over time. forget-rag adds a forgetting layer so they don't.

[![License](https://img.shields.io/badge/license-MIT-blue)](LICENSE)
[![Status](https://img.shields.io/badge/status-alpha-orange)](#status)

## The problem

Most RAG systems assume data is append-only. After 6–12 months of use:

- Search becomes slower (more vectors to scan)
- Quality drops (stale answers compete with fresh ones)
- Storage and embedding costs balloon
- Nobody knows what to delete

We measured this on a 4-year personal knowledge corpus.
[See benchmark →](docs/benchmark.md) *(coming Week 2)*

## What forget-rag does

A drop-in forgetting layer for any RAG system. Three primitives:

1. **Heat score** — every chunk has a decay function based on access frequency + recency
2. **L1/L2/L3 tiered storage** — modeled after CPU cache hierarchy (see below)
3. **Graceful evolution** — you decide *when* and *what* to forget, never auto-deletes

### Why three tiers? (L1 / L2 / L3)

Knowledge has different access patterns. Treating everything the same is wasteful.

| Tier | What lives here | Indexes | Cost | Example |
|------|----------------|---------|------|---------|
| **L1 — Hot** | Recently created or accessed; frequently queried | Vector + FTS5 | Highest | Last week's meeting notes, current project docs |
| **L2 — Warm** | Older but still relevant; occasionally needed | FTS5 only (no vector) | Medium | 3-month-old playbooks, last quarter's OKRs |
| **L3 — Cold** | Rarely accessed; might never be needed again | Archived JSON, not in active index | Lowest | 5-year-old onboarding docs, deprecated runbooks |

Each tier has a soft size cap (default: L1=1k, L2=10k, L3=unlimited). When a chunk's heat drops below the threshold, it falls one tier. When it gets searched (and matched), it can be promoted back up.

**Result:** vector index stays small and fast, but nothing is lost. Cold knowledge is still searchable via FTS5 — it just doesn't compete for vector slots.

## Quick start

```python
from forget_rag import ForgettingMemory

memory = ForgettingMemory(
    backend="sqlite",
    decay_halflife_days=30,
    tiers={"L1": 1000, "L2": 10000, "L3": "unlimited"}
)

memory.add("Some knowledge chunk", tags=["meeting", "2026-Q1"])
results = memory.search("query", limit=5)  # auto-promotes hot chunks
report = memory.health_check()             # what should be forgotten?
```

## What's included

- [`packages/forget-rag`](packages/forget-rag) — Python library (this is what you install)
- [`packages/mem-broom`](packages/mem-broom) — CLI tool that uses forget-rag to clean up Claude Code / Cursor memory files *(coming Week 3)*
- [`docs/architecture.md`](docs/architecture.md) — diagrams and design rationale

## Why this exists

I'm a PM who built a personal knowledge engine over 2 months. After running it daily on 4 years of accumulated content, I noticed search degrading. The fix wasn't a better embedding model — it was admitting that **knowledge has a half-life**.

Enterprise RAG systems (Xerno, Glean, Notion AI) all face this. They just don't talk about it. forget-rag is the open piece of that puzzle.

## Status

**v0.1.0-alpha** — Bootstrap phase. Looking for early users and feedback.

## Roadmap

- [ ] v0.1: SQLite backend + LangChain adapter + mem-broom CLI
- [ ] v0.2: LlamaIndex / Chroma adapters + MCP server for mem-broom
- [ ] v0.3: Multi-tenant namespace + benchmark suite
- [ ] v1.0: Production hardening + observability

## License

MIT. Use it, ship it, fork it.
