[English](SPEC.md) | [繁體中文](SPEC.zh-TW.md)

# forget-rag — Minimal Spec v0.1

## Design principles
1. **Library, not service** — runs in user's process, no daemon
2. **Backend-agnostic** — SQLite default, adapters for LangChain/LlamaIndex
3. **Never auto-deletes** — surfaces decisions, user commits
4. **Boring tech** — SQLite, NumPy, no exotic deps

## Core API

```python
from typing import Literal

class ForgettingMemory:
    def __init__(
        self,
        backend: Literal["sqlite", "langchain", "llamaindex"] = "sqlite",
        sqlite_path: str = "forget_rag.db",
        decay_halflife_days: float = 30.0,
        tiers: dict[str, int | str] | None = None,
        namespace: str = "default",   # multi-tenant prep
    ): ...

    def add(self, text: str, tags: list[str] | None = None,
            metadata: dict | None = None) -> str:
        """Returns chunk_id."""

    def search(self, query: str, limit: int = 5) -> list["Chunk"]:
        """Hybrid: BM25 + vector + heat boost. Promotes accessed chunks."""

    def health_check(self) -> "HealthReport":
        """Returns {duplicates, stale, tier_distribution, suggested_forgets}"""

    def forget(self, chunk_ids: list[str]) -> int:
        """Soft delete. Reversible within 30 days."""

    def stats(self) -> "Stats": ...
```

## Heat score formula

```
heat(chunk, t) = base_score * exp(-ln(2) * age_days / halflife)
                + access_bonus * recent_accesses
                + tag_weight   # configurable
```

Stored as derived field, recomputed on read (cached 1h).

## Tier transitions

```
L1 (vector + FTS) ──heat < L1_threshold──▶ L2 (FTS only)
L2 (FTS only)     ──heat < L2_threshold──▶ L3 (archived JSON)
L3                ──user commit──────────▶ deleted
```

Promotion: a search hit on L2/L3 raises `access_count` and recomputes heat. If new heat crosses threshold, chunk moves up next maintenance pass.

## Storage schema (SQLite default)

```sql
CREATE TABLE chunks (
    id TEXT PRIMARY KEY,
    namespace TEXT NOT NULL DEFAULT 'default',
    text TEXT NOT NULL,
    tags TEXT,                       -- JSON array
    metadata TEXT,                   -- JSON object
    tier TEXT NOT NULL DEFAULT 'L1',
    base_score REAL DEFAULT 1.0,
    last_access TEXT,
    access_count INTEGER DEFAULT 0,
    created_at TEXT,
    forgotten_at TEXT                -- soft delete sentinel
);

CREATE VIRTUAL TABLE chunks_fts USING fts5(text, tags, content='chunks');
CREATE TABLE chunks_vec (id TEXT PRIMARY KEY, embedding BLOB);
```

## Repo layout

```
forget-rag/
├── README.md / README.zh-TW.md
├── SPEC.md / SPEC.zh-TW.md
├── ROADMAP.md / ROADMAP.zh-TW.md
├── LICENSE (MIT)
├── pyproject.toml                 # uv workspace root
├── packages/
│   ├── forget-rag/                # core lib
│   │   ├── pyproject.toml
│   │   ├── src/forget_rag/
│   │   │   ├── __init__.py
│   │   │   ├── memory.py          # ForgettingMemory main class
│   │   │   ├── heat.py            # decay scoring
│   │   │   ├── tiers.py           # tier transitions
│   │   │   ├── backends/
│   │   │   │   ├── sqlite.py
│   │   │   │   └── langchain.py
│   │   │   └── benchmark.py
│   │   └── tests/
│   └── mem-broom/                 # CLI on top of forget-rag (v0.2)
│       ├── pyproject.toml
│       └── src/mem_broom/
│           ├── cli.py
│           └── readers/claude_code.py
├── docs/
│   ├── architecture.md / .zh-TW.md
│   ├── benchmark.md               # Week 2
│   └── why-forgetting.md          # Week 4
└── examples/
    └── 01_basic_usage.py
```

## Out of scope for v0.1
- Web UI / dashboard
- Multi-user auth
- Distributed backend
- Custom embedding training
- LlamaIndex / Chroma adapters
- MCP server (mem-broom v0.2)
