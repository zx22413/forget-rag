[English](ROADMAP.md) | [繁體中文](ROADMAP.zh-TW.md)

# Roadmap & Week 1 Plan

## Week 1: Core lib bootstrap (Mon–Sun)

### Mon — Project skeleton
- [x] Create empty `forget-rag` repo on GitHub (PUBLIC, MIT, no Brain content)
- [x] Set up monorepo layout (per SPEC.md)
- [x] `pyproject.toml` with `uv` workspace, Python 3.11+
- [x] CI: GitHub Actions running pytest on push (5-min job)
- [x] First commit: `chore: initial scaffold`

### Tue — SQLite backend + heat score
- [x] Implement `chunks` schema + FTS5 virtual table
- [x] `heat.py`: decay function with `decay_halflife_days` param
- [x] Unit tests for heat decay (3 cases: fresh / aged / boosted)
- [x] Commit: `feat: sqlite backend + heat decay`

### Wed — Add / search / forget
- [x] `ForgettingMemory.add()` — insert + FTS index
- [x] `ForgettingMemory.search()` — BM25 + heat boost (skip vector wave 1)
- [x] `ForgettingMemory.forget()` — soft delete
- [x] Tests for round-trip
- [x] Commit: `feat: add/search/forget primitives`

### Thu — Tier transitions
- [x] `tiers.py`: L1→L2→L3 logic with thresholds
- [x] `health_check()` returns suggestions
- [x] Tests with fast-forwarded clock
- [x] Commit: `feat: tiered storage`

### Fri — Vector layer (optional)
- [ ] Add bge-m3 embedding via `sentence-transformers` or `ollama`
- [ ] RRF combine BM25 + vector
- [ ] If too much, push to weekend
- [ ] Commit: `feat: hybrid search with vector`

### Sat — Examples + dogfood
- [x] `examples/01_basic_usage.py` — runnable in 30 seconds
- [x] Run it on a fake corpus (back-dated chunks demonstrate decay)
- [x] Capture CLI output for README (`examples/01_basic_usage.out.txt`)
- [x] Commit: `docs: examples`

### Sun — Public-ready README
- [x] README v0 (already done as part of bootstrap)
- [x] Add architecture diagram (mermaid in `docs/architecture.md` — renders inline on GitHub)
- [ ] Push everything; **don't launch yet** (Week 2 target)
- [x] Commit: `docs: v0 README + diagram` (covered by initial scaffold)

## Week 2: LangChain adapter + benchmark

Decisions locked end of Week 1:
- Adapter shape: **`BaseRetriever`** only (not `VectorStore` — forget-rag has no vector layer in v0.1, faking one would mislead users). Plus a **Chroma integration example** so existing Chroma users see how to wrap forget-rag around it.
- Benchmark corpus: **synthetic** (deterministic timestamps, reproducible) — no Wikipedia/BEIR in v0.1.
- Metrics: **latency** + **Precision@5** only.

### Mon — LangChain spike + scaffolding
- [x] Research `langchain-core` `BaseRetriever` interface (Context7 + GitHub search)
- [x] Add `langchain-core>=0.3` as optional dep group `[langchain]`
- [x] Create `adapters/__init__.py` and `adapters/langchain.py` skeleton
- [x] Smoke test: import works without `langchain-core` installed (graceful)
- [x] Commit: `feat(adapter): langchain scaffolding`

### Tue — ForgettingRetriever
- [x] `ForgettingRetriever` extends `BaseRetriever`
- [x] `_get_relevant_documents(query)` → `list[Document]` with metadata (id, heat, tier, score, tags)
- [x] async `_aget_relevant_documents` (run sync in executor for v0.1)
- [x] Tests with langchain-core installed in dev group
- [x] Commit: `feat(adapter): forgetting retriever sync + async`

### Wed — Benchmark harness
- [x] `benchmark.py`: `make_corpus(n, age_distribution, seed)` — synthetic generator
- [x] `make_query_set(corpus, n, seed)` — queries with ground-truth relevant ids
- [x] `measure(memory, queries)` — returns latency p50/p95 + precision@5
- [x] Tests for harness reproducibility (same seed → same output)
- [x] Commit: `feat(bench): synthetic corpus + metric collector`

### Thu — Run experiments
- [x] Three configs: A=pure BM25, B=BM25+heat, C=B+maintenance
- [x] Three corpus sizes: 1k / 10k / 100k chunks
- [x] Save raw JSON to `docs/benchmark_data/results.json`
- [x] Generate ASCII tables for embedding in markdown
- [x] Commit: `feat(bench): heat vs no-heat experiments`

### Fri — Write up
- [x] `docs/benchmark.md` — method, results, analysis, "what this proves / doesn't prove"
- [x] `docs/benchmark.zh-TW.md` — Chinese mirror
- [x] README: replace `(coming Week 2)` with real link
- [x] Commit: `docs(bench): write-up + readme link`

### Sat — LangChain + Chroma examples
- [x] `examples/02_langchain_retriever.py` — minimal retriever in a chain
- [x] `examples/03_chroma_with_forget_rag.py` — Chroma does vector recall, forget-rag re-ranks with heat
- [x] Bilingual docstrings + captured `.out.txt` transcripts
- [x] Commit: `docs: langchain + chroma examples`

### Sun — Buffer / push
- [x] Smoke from clean clone (`uv sync && pytest && examples`)
- [x] Push everything
- [x] Commit: `chore: week 2 close`

## Week 3: mem-broom CLI

Decisions confirmed end of Week 2:
- CLI framework: **typer** (same author as FastAPI; type-hint driven `--help`, pairs nicely with `rich` for tables)
- Output: **human-readable default + `--json` flag** (for pipes / scripts)
- `restore` subcommand: **skipped**, deferred to Week 4 / v0.2 (schema has `forgotten_at`, but a backend API still needs to be added)

### Mon — Scaffold
- [x] Create standalone subpackage at `packages/mem-broom/` (sibling to forget-rag)
- [x] `pyproject.toml`: depend on `forget-rag` (workspace), `typer>=0.12`, `rich>=13`
- [x] Entry point: `mem-broom = mem_broom.cli:app`
- [x] Typer skeleton in `mem_broom/cli.py` (empty app + version flag)
- [x] Smoke test: `mem-broom --help` runs
- [x] Commit: `feat(cli): mem-broom scaffolding`

### Tue — Read-only commands: stats + health
- [x] `mem-broom stats [--db PATH] [--json]`: chunk count, tier distribution, hottest/coldest
- [x] `mem-broom health [--db PATH] [--json]`: run `health_check()`, list forget suggestions
- [x] `--json` writes to stdout; human-readable uses `rich.Table`
- [x] Unit tests via `typer.testing.CliRunner` against an in-memory DB
- [x] Commit: `feat(cli): stats + health commands`

### Wed — Write commands: maintain + forget
- [x] `mem-broom maintain [--db PATH] [--json]`: run `maintenance()`, print new tier distribution
- [x] `mem-broom forget <id>... [--yes] [--db PATH]`: soft-delete; confirm by default
- [x] Confirmation via `typer.confirm`; `--yes` skips
- [x] Tests: declined confirm doesn't delete; `--yes` actually deletes
- [x] Commit: `feat(cli): maintain + forget commands`

### Thu — search + add
- [x] `mem-broom search <query> [--limit N] [--db PATH] [--json]`
- [x] `mem-broom add <text> [--tag T]... [--db PATH]`
- [x] `add` supports stdin pipe: missing `<text>` reads stdin (`cat foo.md | mem-broom add`)
- [x] Tests: pipe behaviour + tag parsing
- [x] Commit: `feat(cli): search + add commands`

### Fri — Polish: output format + error handling
- [ ] Unified JSON envelope: `{"ok": bool, "data": ..., "error": null}`
- [ ] Friendly errors when DB path is missing / namespace is empty
- [ ] Global `--version` and `--namespace` flags
- [ ] Commit: `feat(cli): json envelope + error messages`

### Sat — Examples + docs
- [ ] `examples/04_cli_walkthrough.md`: end-to-end add → search → health → forget
- [ ] README mem-broom section (bilingual)
- [ ] mem-broom's own `packages/mem-broom/README.md`
- [ ] Commit: `docs: mem-broom cli walkthrough + readme`

### Sun — Buffer / push
- [ ] Smoke from clean clone: `uv sync && pytest && mem-broom --help`
- [ ] Push everything
- [ ] Commit: `chore: week 3 close`

## Week 4: Launch + write-up
*(detailed plan written end of Week 3)*

---

## Time budget

- forget-rag: ≤ 10 hours / week
- Brain maintenance: continue normally, don't sacrifice
- If a day blows up, slip the day, don't compress quality

## Discipline rules

1. **One commit per checkbox**, with conventional commit message
2. **Tests pass before commit** (CI catches it anyway)
3. **No real Brain data** in any test/example/screenshot
4. **README must work** — anyone cloning it should
   `pip install -e packages/forget-rag && python examples/01_basic_usage.py`
   and see output
