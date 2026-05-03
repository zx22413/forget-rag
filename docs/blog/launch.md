[English](launch.md) | [繁體中文](launch.zh-TW.md)

# Your RAG is getting dumber. Here's the receipt.

Pick any RAG system that's been in production for six months. Run a
query that should return the latest version of a document you've
revised three times. Watch it confidently surface the second draft
from April.

This isn't a model problem. It's a **storage** problem, and almost
nobody is solving it.

[`forget-rag`](https://github.com/zx22413/forget-rag) is a small Python
library — under 1,000 lines of core code — that adds a forgetting layer
to whatever retrieval stack you're already using. This post is about
why that's necessary and what the v0.1 release actually does.

## The append-only assumption

Most RAG tutorials walk you through three steps: chunk your documents,
embed them, store the embeddings. Some include a re-ranking step.
Almost none cover what happens when you do this for a year.

The default behavior of every popular vector store — Chroma, Weaviate,
pgvector, Pinecone, FAISS — is **append-only**. You add embeddings.
They sit there. There is no built-in mechanism for "this chunk is now
stale" or "the user revised this last week, prefer it over the version
from three months ago." If you want eviction, you write it yourself.

In practice, almost nobody does. So you end up with:

- **Search slows down.** More vectors means slower scans, especially
  when you exceed your index's HNSW or IVF tuning sweet spot.
- **Quality drops.** Stale answers compete with fresh ones, and the
  embedder has no concept of recency.
- **Storage and embedding costs balloon.** Every revision adds chunks;
  none are removed.
- **Nobody knows what to delete.** Even if you wanted to clean up,
  the system gives you no signal about which chunks are still valuable.

The first three are annoying. The fourth is the one that actually kills
projects. By the time you notice your RAG is slow and dumb, you have
no way to tell which chunks to evict — they all look equally
"document-y" from outside.

## What forgetting looks like

Human memory doesn't work this way. You don't have a uniform record of
every fact you've ever encountered, with equal retrieval probability.
Things you used yesterday are easy to recall. Things you used five
years ago and never since are functionally gone, even if technically
still in there somewhere.

Tulving and Pearlstone showed this in 1966 with a cued-recall
experiment: subjects could only retrieve a small fraction of a list
unaided, but with category cues, retrieval shot up. The information
was *available* but not *accessible* — and "accessibility" decayed
with time and disuse.

`forget-rag` is built around three primitives that mirror this:

### 1. Heat score

Every chunk has a numeric `heat` value. It's a function of:

- **Recency** — when was the chunk last accessed?
- **Frequency** — how many times has it been retrieved?
- **A configurable decay half-life** — default 30 days

Each search updates `last_access` and increments `access_count`. Over
time, chunks that nobody queries cool off. Chunks that get hit
frequently stay warm.

This isn't an embedding trick — it's a separate scalar stored alongside
the chunk in SQLite. Search results are re-ranked using it.

### 2. Tiered storage (L1 / L2 / L3)

Hot, warm, and cold chunks have different access patterns, so
`forget-rag` stores them differently — modeled after a CPU cache:

| Tier | What lives here | Indexed via | Cost |
|------|----------------|-------------|------|
| **L1** | Recently active, frequently queried | Vector + FTS5 | Highest |
| **L2** | Older but still occasionally relevant | FTS5 only | Medium |
| **L3** | Rarely accessed, archived | Explicit lookup | Lowest |

When a chunk's heat drops below a tier's threshold, it falls one tier.
When it gets searched and matched, it can promote back up. Soft caps
on each tier (default L1=1k, L2=10k, L3=unlimited) keep the active
vector index small and fast.

The result: **the vector index stays bounded**, but nothing is lost.
Cold knowledge is still searchable via FTS5 — it just doesn't compete
for vector slots.

### 3. Soft delete, never automatic

`forget-rag` will never delete data without explicit instruction. The
`forget()` API marks a chunk with a `forgotten_at` timestamp. The
schema retains the row. A future `restore()` (planned for v0.2) can
unforget it.

This is deliberate. Auto-delete is the failure mode of every "smart"
memory system — it's how you lose data you didn't realize you needed.
`forget-rag` instead surfaces forgetting *recommendations* through
`health_check()` and lets you decide.

## Does any of this actually help? Numbers.

We ran a synthetic benchmark. The setup is fully reproducible — run
`uv run python scripts/run_benchmark.py` to verify — and detailed in
[docs/benchmark.md](https://github.com/zx22413/forget-rag/blob/main/docs/benchmark.md).

The corpus is deliberately adversarial for pure BM25: 10 topics, where
every chunk in a topic shares the same keyword. The "correct" answer
to a topic query is the **freshest 3 chunks**. Pure BM25 has no signal
to prefer the freshest version — it sees the keyword in all of them
and shrugs.

Three configurations:

- `bm25_only` — pure BM25, no heat boost
- `bm25_heat` — BM25 + heat re-ranking
- `bm25_heat_m` — same as above, with periodic `maintenance()`

```
config            n_chunks   p50 ms     P@1     P@5
bm25_only             1000     0.43   11.0%   50.0%
bm25_heat             1000     0.45   59.0%   59.0%
bm25_only            10000     1.28    0.0%    7.0%
bm25_heat            10000     3.80   32.0%   32.0%
bm25_only           100000    25.97    0.0%    0.0%
bm25_heat           100000    13.77    0.0%    0.0%
```

Two things to notice.

**At 1k chunks, heat takes Precision@1 from 11% to 59% — a 5.4× lift.**
At 10k it's 0% to 32%. The latency hit is well under 25%, and at 100k
heat ranking is actually *faster* (different code path).

**At 100k chunks, both approaches collapse to 0%.** This is the part
the benchmark write-up is honest about: at 100k there are ~10k chunks
per topic, and the search candidate pool is fixed at `max(limit*4, 20)`.
The freshest 3 are almost never inside that 20-row pool when BM25
scores are uniform within a topic. Heat can't promote what BM25 didn't
surface.

The fix — **tier-aware search**, where the query first filters to L1
and only falls back to broader pools if empty — is on the v0.2 list.

## What this proves and what it doesn't

What it proves:

- Heat-based re-ranking transforms the freshness-sensitive case where
  pure BM25 picks at random.
- The latency cost is small enough to ignore at the scales where
  precision actually improves.
- The architecture is sound — FTS5 + a heat scalar in SQLite is enough
  to demonstrate the primitives without dragging in a vector DB.

What it doesn't prove:

- Numbers from synthetic corpora don't transfer to real text. Real
  documents have semantic overlap, typos, intentional ambiguity, and
  multiple valid "freshest" answers. We're claiming the *direction* is
  real — heat helps freshness ranking — not that you'll see 5× lifts
  on your data.
- v0.1 is single-backend (SQLite + FTS5). The vector layer ships in
  v0.2. If you need vector search today, the v0.1 LangChain adapter
  lets you compose `forget-rag` *on top of* an existing Chroma or
  pgvector setup — heat re-ranking applied to vector recall.

## What this isn't

A few common misreadings, addressed up front.

**It's not a vector database.** It uses SQLite + FTS5 for v0.1. Vector
support arrives in v0.2 (planned: `bge-m3` via `sentence-transformers`,
RRF for hybrid retrieval).

**It's not a RAG framework.** It's a forgetting *layer*. Bring your own
chunker, embedder, prompt template. The library exposes
`add` / `search` / `forget` / `health_check` / `maintenance` and a
LangChain `BaseRetriever` adapter. Compose it however you want.

**It's not magic.** It will not make a bad retrieval pipeline good.
It addresses one specific failure mode — knowledge bases that get
worse over time — and it does so by making that failure mode *visible*
and *actionable*.

## Who's it for, who's it not for

**You'll probably want this if:**

- You have a knowledge base that gets revised over time (engineering
  docs, meeting notes, support runbooks, personal notes).
- You've noticed your RAG getting slower or returning stale answers
  and don't want to write the eviction logic yourself.
- You want forgetting recommendations rather than aggressive auto-pruning.
- You're already using LangChain or composing your own retrieval — the
  adapter slots in.

**You probably don't need this if:**

- Your corpus is genuinely append-only and immutable (legal contracts
  with effective dates, historical archives) — there's nothing to
  forget.
- You only care about static benchmarks like BEIR — these have no
  notion of recency, so heat scoring is irrelevant.
- You need a turnkey RAG-in-a-box. `forget-rag` is a primitive, not
  a product.

## Try it

```bash
pip install forget-rag

# with the LangChain adapter
pip install "forget-rag[langchain]"

# the companion CLI for ad-hoc memory hygiene
pip install mem-broom
```

Five-line example:

```python
from forget_rag import ForgettingMemory

memory = ForgettingMemory(backend="sqlite", decay_halflife_days=30)
memory.add("Some chunk", tags=["meeting", "2026-Q1"])
results = memory.search("query", limit=5)   # auto-promotes hot chunks
report = memory.health_check()              # what should be forgotten?
```

For a guided tour of the CLI:
[examples/04_cli_walkthrough.md](https://github.com/zx22413/forget-rag/blob/main/examples/04_cli_walkthrough.md).

For the full benchmark methodology:
[docs/benchmark.md](https://github.com/zx22413/forget-rag/blob/main/docs/benchmark.md).

## What's coming in v0.2

The v0.1 release is intentionally narrow — it ships the three
forgetting primitives and proves the heat-ranking thesis with
reproducible numbers. The v0.2 release plans to address the obvious
gaps:

- **Vector layer.** `bge-m3` embeddings, RRF for hybrid BM25+vector
  retrieval. The architecture already accommodates this — L1 chunks
  carry vector embeddings; v0.2 wires up the actual recall path.
- **Tier-aware search.** Query L1 first, fall back to broader pools
  only if empty — the fix for the 100k benchmark collapse.
- **Restore.** The schema already has `forgotten_at`; v0.2 exposes
  the `restore()` API and a `mem-broom restore <id>` subcommand.
- **More backends.** Postgres + pgvector is the most-requested.

`forget-rag` is alpha software. The API may change before v1.0. Issues,
discussions, and PRs welcome:
[github.com/zx22413/forget-rag](https://github.com/zx22413/forget-rag).

---

*forget-rag is MIT licensed. The benchmark numbers in this post are
deterministic and reproducible from the seeded corpus generator.*
