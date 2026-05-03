[English](README.md) | [繁體中文](README.zh-TW.md)

# forget-rag

> RAG 系統用久了會變笨。forget-rag 加上一層遺忘機制，讓它不會。

[![License](https://img.shields.io/badge/license-MIT-blue)](LICENSE)
[![Status](https://img.shields.io/badge/status-alpha-orange)](#狀態)

## 痛點

多數 RAG 系統假設資料只增不刪。用 6–12 個月後：

- 搜尋變慢（向量越來越多）
- 品質下降（過時答案跟新答案打架）
- 儲存與 embedding 成本爆炸
- 沒人知道該刪什麼

我用 4 年累積的個人知識庫實測過這件事。
[看 benchmark →](docs/benchmark.zh-TW.md) *(Week 2 提供)*

## forget-rag 在做什麼

可以掛在任何 RAG 系統上的遺忘層。三個基礎元件：

1. **熱度分數（heat score）** — 每個 chunk 都有衰減函數，根據存取頻率與時間
2. **L1/L2/L3 三層儲存** — 模仿 CPU cache 階層（見下方）
3. **漸進演化** — 你決定「何時」「忘什麼」，永不自動刪除

### 為什麼分三層？（L1 / L2 / L3）

知識的存取模式不一樣，全部用同一種方式存是浪費。

| 層級 | 存什麼 | 索引 | 成本 | 例子 |
|------|-------|------|------|------|
| **L1 — 熱** | 剛產生或最近用過、被頻繁查 | 向量 + FTS5 | 最高 | 上週會議記錄、進行中的專案文件 |
| **L2 — 溫** | 舊但仍有用、偶爾會查 | 只剩 FTS5（不做向量） | 中等 | 3 個月前的 playbook、上季 OKR |
| **L3 — 冷** | 幾乎不查、可能再也用不到 | 歸檔成 JSON，不進 active index | 最低 | 5 年前的入職文件、過時的 runbook |

每層有 soft 上限（預設 L1=1k、L2=10k、L3=無限）。chunk 的熱度低於閾值就掉一層；被搜到（且命中）可以升回去。

**效果：** 向量索引保持小而快，但不丟資料。冷的知識還是能用 FTS5 找到，只是不跟熱資料搶向量空間。

## 快速開始

```python
from forget_rag import ForgettingMemory

memory = ForgettingMemory(
    backend="sqlite",
    decay_halflife_days=30,
    tiers={"L1": 1000, "L2": 10000, "L3": "unlimited"}
)

memory.add("某段知識內容", tags=["meeting", "2026-Q1"])
results = memory.search("查詢", limit=5)   # 自動把熱資料拉上來
report = memory.health_check()             # 列出哪些可以忘
```

## 內容

- [`packages/forget-rag`](packages/forget-rag) — Python 函式庫（你會 pip install 的就是這個）
- [`packages/mem-broom`](packages/mem-broom) — CLI 工具，用 forget-rag 整理 Claude Code / Cursor 的記憶檔 *(Week 3 提供)*
- [`docs/architecture.zh-TW.md`](docs/architecture.zh-TW.md) — 架構圖與設計理由

## 為什麼存在

我是一個 PM，花 2 個月做出個人知識引擎。每天用、累積 4 年內容後，搜尋品質開始下滑。解法不是換更好的 embedding 模型——是承認**知識有半衰期**。

企業級 RAG（Xerno、Glean、Notion AI）都遇到同樣問題，只是不講。forget-rag 把這片拼圖開源出來。

## 狀態

**v0.1.0-alpha** — 啟動階段。徵求早期使用者與回饋。

## 路線圖

- [ ] v0.1：SQLite 後端 + LangChain adapter + mem-broom CLI
- [ ] v0.2：LlamaIndex / Chroma adapter + mem-broom MCP server
- [ ] v0.3：多租戶 namespace + 完整 benchmark suite
- [ ] v1.0：production 強化 + 可觀測性

## 授權

MIT。拿去用、拿去 ship、拿去 fork。
