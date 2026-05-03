[English](ROADMAP.md) | [繁體中文](ROADMAP.zh-TW.md)

# Roadmap & Week 1 計畫

## Week 1：核心 lib bootstrap

### 一 — 專案骨架
- [x] 建空的 `forget-rag` repo（公開、MIT、不含 Brain 內容）
- [x] monorepo 目錄按 SPEC.md 擺好
- [x] `pyproject.toml` 用 `uv` workspace，Python 3.11+
- [x] CI：GitHub Actions 跑 pytest（5 分鐘工作）
- [x] 第一個 commit：`chore: initial scaffold`

### 二 — SQLite 後端 + 熱度分數
- [x] `chunks` schema + FTS5 虛擬表
- [x] `heat.py`：衰減函數，`decay_halflife_days` 參數
- [x] 熱度單元測試（3 case：新鮮 / 老舊 / 加成）
- [x] commit：`feat: sqlite backend + heat decay`

### 三 — Add / Search / Forget
- [x] `ForgettingMemory.add()` — 寫入 + FTS 索引
- [x] `ForgettingMemory.search()` — BM25 + 熱度加權（v0.1 第一波先跳過向量）
- [x] `ForgettingMemory.forget()` — soft delete
- [x] round-trip 測試
- [x] commit：`feat: add/search/forget primitives`

### 四 — 分層轉移
- [x] `tiers.py`：L1→L2→L3 邏輯與閾值
- [x] `health_check()` 回建議
- [x] 用 fast-forward 時鐘做測試
- [x] commit：`feat: tiered storage`

### 五 — 向量層（選做）
- [ ] 用 `sentence-transformers` 或 `ollama` 加 bge-m3
- [ ] RRF 合併 BM25 + 向量
- [ ] 來不及就推到週末
- [ ] commit：`feat: hybrid search with vector`

### 六 — 範例 + 自用
- [x] `examples/01_basic_usage.py` — 30 秒能跑完
- [x] 在假資料上跑（用 back-date 時間戳呈現衰減）
- [x] CLI 輸出存檔供 README 用（`examples/01_basic_usage.out.txt`）
- [x] commit：`docs: examples`

### 日 — 公開版 README
- [x] README v0（bootstrap 階段已完成）
- [x] 加架構圖（`docs/architecture.md` 用 mermaid，GitHub 直接 render）
- [ ] 全部 push；**還不要 launch**（Week 2 才發）
- [x] commit：`docs: v0 README + diagram`（已在初始 scaffold 包含）

## Week 2：LangChain adapter + benchmark

Week 1 末確認的決策：
- Adapter 形式：**只做 `BaseRetriever`**（不做 `VectorStore`——v0.1 沒向量層，硬扮等於騙用戶）。另外加一個 **Chroma 整合範例**，讓現有 Chroma 用戶看到怎麼把 forget-rag 包在外面。
- Benchmark 語料：**合成假資料**（時間戳完全可控、可重現）——不用 Wikipedia / BEIR。
- 指標：**搜尋延遲**（速度）+ **Precision@5**（答案準度）兩項。

### 一 — LangChain spike + scaffolding
- [x] 研究 `langchain-core` 的 `BaseRetriever` 介面（Context7 + GitHub 搜尋）
- [x] 加 `langchain-core>=0.3` 到 optional dep group `[langchain]`
- [x] 建 `adapters/__init__.py` 與 `adapters/langchain.py` 骨架
- [x] Smoke test：沒裝 `langchain-core` 時 import 也不會炸
- [x] commit：`feat(adapter): langchain scaffolding`

### 二 — ForgettingRetriever
- [x] `ForgettingRetriever` 繼承 `BaseRetriever`
- [x] `_get_relevant_documents(query)` → `list[Document]`，metadata 含 id/heat/tier/score/tags
- [x] async `_aget_relevant_documents`（v0.1 用 executor 跑同步版）
- [x] dev group 裝 langchain-core 跑測試
- [x] commit：`feat(adapter): forgetting retriever sync + async`

### 三 — Benchmark harness
- [x] `benchmark.py`：`make_corpus(n, age_distribution, seed)` 合成生成器
- [x] `make_query_set(corpus, n, seed)`：含 ground-truth 相關 id
- [x] `measure(memory, queries)`：回延遲 p50/p95 + precision@5
- [x] 可重現性測試（同 seed 同結果）
- [x] commit：`feat(bench): synthetic corpus + metric collector`

### 四 — 跑實驗
- [x] 三組設定：A=純 BM25、B=BM25+heat、C=B+maintenance
- [x] 三種 corpus size：1k / 10k / 100k chunks
- [x] 原始 JSON 存到 `docs/benchmark_data/results.json`
- [x] 產 ASCII 表格供 markdown 嵌入
- [x] commit：`feat(bench): heat vs no-heat experiments`

### 五 — Write up
- [ ] `docs/benchmark.md`：方法、結果、分析、「證明了什麼 / 沒證明什麼」
- [ ] `docs/benchmark.zh-TW.md`：中文鏡像
- [ ] README：把 `(coming Week 2)` 換成真連結
- [ ] commit：`docs(bench): write-up + readme link`

### 六 — LangChain + Chroma 範例
- [ ] `examples/02_langchain_retriever.py`：最小的 retriever 接到 chain
- [ ] `examples/03_chroma_with_forget_rag.py`：Chroma 負責向量召回，forget-rag 用 heat 重排
- [ ] 雙語 docstring + `.out.txt` transcript 留檔
- [ ] commit：`docs: langchain + chroma examples`

### 日 — Buffer / push
- [ ] 從乾淨 clone 跑 smoke（`uv sync && pytest && examples`）
- [ ] 全部 push
- [ ] commit：`chore: week 2 close`

## Week 3：mem-broom CLI
*(Week 2 結束時詳細規劃)*

## Week 4：Launch + write-up
*(Week 3 結束時詳細規劃)*

---

## 時間預算

- forget-rag：每週 ≤ 10 小時
- Brain 維護：照常進行，不要犧牲
- 哪天爆掉，順延，不壓縮品質

## 紀律規則

1. **一個 checkbox 一個 commit**，conventional commit message
2. **commit 前測試要過**（CI 也會抓）
3. **任何測試/範例/截圖都不能用 Brain 真實資料**
4. **README 必須能跑** — 任何人 clone 後
   `pip install -e packages/forget-rag && python examples/01_basic_usage.py`
   要看到輸出
