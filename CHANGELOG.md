# Changelog

English | [繁體中文](CHANGELOG.zh-TW.md)

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.0] - 2026-05-06

Initial public release. A drop-in forgetting layer for RAG systems with SQLite + FTS5 backend, heat-decay scoring, three-tier storage, LangChain integration, and a companion CLI.

### Added

#### Core library — `forget-rag`

- SQLite + FTS5 storage backend with full-text indexing
- Heat-score decay: exponential, with access bonus and tag weight
- `add()` / `search()` / `forget()` primitives — `forget()` is soft-delete (preserves history via `forgotten_at`)
- L1 / L2 / L3 tiered storage with automatic transition rules
- `health_check()` — surfaces forget candidates and tier drift
- BM25 + heat-boost ranking (no vector layer in v0.1; deferred to v0.2)

#### LangChain adapter

- `ForgettingRetriever` extends `BaseRetriever`
- Sync and async `_get_relevant_documents`
- Returns `Document` with full metadata (id, heat, tier, score, tags)
- Optional dependency group `[langchain]` — graceful import without it installed

#### Benchmark harness

- `make_corpus(n, age_distribution, seed)` — synthetic, deterministic
- `make_query_set(corpus, n, seed)` — queries with ground-truth ids
- `measure(memory, queries)` — latency p50/p95 + Precision@5
- Three configs: pure BM25, BM25 + heat, BM25 + heat + maintenance
- **Result**: heat boost lifts Precision@1 from 0% to 32% at 10k chunks with <25% latency overhead. Full write-up in [docs/benchmark.md](docs/benchmark.md).

#### CLI — `mem-broom`

- `mem-broom stats` — chunk count, tier distribution, hottest/coldest
- `mem-broom health` — list forget suggestions
- `mem-broom maintain` — run tier transitions, print delta
- `mem-broom forget <id>...` — soft-delete with confirmation (`--yes` to skip)
- `mem-broom search <query>` — query the store
- `mem-broom add <text>` — insert; supports stdin pipe (`cat foo.md | mem-broom add`)
- `--json` flag — unified envelope `{ok, data, error}`
- Global `--namespace` and `--version` flags
- Friendly errors when DB path is missing or namespace is empty

#### Examples

- [`examples/01_basic_usage.py`](examples/01_basic_usage.py) — runnable in 30 seconds
- [`examples/02_langchain_retriever.py`](examples/02_langchain_retriever.py) — minimal retriever in a chain
- [`examples/03_chroma_with_forget_rag.py`](examples/03_chroma_with_forget_rag.py) — Chroma vector recall + forget-rag heat re-rank
- [`examples/04_cli_walkthrough.md`](examples/04_cli_walkthrough.md) — end-to-end CLI walkthrough

#### Project infrastructure

- Bilingual documentation (English + Traditional Chinese): README, ROADMAP, SPEC, benchmark, architecture
- `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md` (Contributor Covenant 2.1), `SECURITY.md`
- GitHub issue templates (bug report, feature request) and PR template
- GitHub Actions CI: pytest on push
- PyPI Trusted Publisher (OIDC) configured for `forget-rag`

### Notes

- **`mem-broom` PyPI publish deferred to post-v0.1.** The PyPI Pending Trusted Publisher form returns 500 when adding a second publisher to a single account (reproduced across multiple project names). Tracked upstream at [pypi/warehouse#20006](https://github.com/pypi/warehouse/issues/20006). v0.1 ships `mem-broom` as a git install or as a wheel/sdist artifact attached to the GitHub Release.
- **Vector embedding layer deferred to v0.2.**
- **`mem-broom restore` deferred to v0.2.** Schema supports it (`forgotten_at` is preserved on soft delete), but the backend API is not yet exposed.

[Unreleased]: https://github.com/zx22413/forget-rag/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/zx22413/forget-rag/releases/tag/v0.1.0
