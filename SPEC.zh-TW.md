[English](SPEC.md) | [繁體中文](SPEC.zh-TW.md)

# forget-rag — Minimal Spec v0.1

## 設計原則
1. **函式庫，不是服務** — 跑在使用者 process 內，不需要 daemon
2. **後端無關** — 預設 SQLite，提供 LangChain/LlamaIndex adapter
3. **絕不自動刪除** — 列出建議，使用者決定
4. **無聊技術優先** — SQLite、NumPy，不引入奇怪依賴

## 核心 API

```python
from typing import Literal

class ForgettingMemory:
    def __init__(
        self,
        backend: Literal["sqlite", "langchain", "llamaindex"] = "sqlite",
        sqlite_path: str = "forget_rag.db",
        decay_halflife_days: float = 30.0,
        tiers: dict[str, int | str] | None = None,
        namespace: str = "default",   # 多租戶預備
    ): ...

    def add(self, text: str, tags: list[str] | None = None,
            metadata: dict | None = None) -> str:
        """回傳 chunk_id。"""

    def search(self, query: str, limit: int = 5) -> list["Chunk"]:
        """混合：BM25 + 向量 + 熱度加權。命中會升熱度。"""

    def health_check(self) -> "HealthReport":
        """回傳 {重複, 過時, 各層分布, 建議遺忘清單}"""

    def forget(self, chunk_ids: list[str]) -> int:
        """軟刪除，30 天內可救回。"""

    def stats(self) -> "Stats": ...
```

## 熱度分數公式

```
heat(chunk, t) = base_score × exp(-ln(2) × age_days / halflife)
                + access_bonus × recent_accesses
                + tag_weight   # 可設定
```

存成衍生欄位，讀取時計算（快取 1 小時）。

## 分層轉移

```
L1（向量 + FTS）── heat < L1 閾值 ──▶ L2（只剩 FTS）
L2（只剩 FTS） ── heat < L2 閾值 ──▶ L3（JSON 歸檔）
L3            ── 使用者確認 ────────▶ 真正刪除
```

升級：L2/L3 的 chunk 被搜到並命中時，`access_count` 加 1 並重算熱度。若超過閾值，下次維護時會升回去。

## 儲存 schema（預設 SQLite）

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
    forgotten_at TEXT                -- 軟刪除標記
);

CREATE VIRTUAL TABLE chunks_fts USING fts5(text, tags, content='chunks');
CREATE TABLE chunks_vec (id TEXT PRIMARY KEY, embedding BLOB);
```

## v0.1 不做的事
- Web UI / dashboard
- 多用戶認證
- 分散式後端
- 自訓 embedding
- LlamaIndex / Chroma adapter
- MCP server（mem-broom v0.2）
