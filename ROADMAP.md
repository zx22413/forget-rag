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
*(detailed plan written end of Week 1)*

## Week 3: mem-broom CLI
*(detailed plan written end of Week 2)*

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
