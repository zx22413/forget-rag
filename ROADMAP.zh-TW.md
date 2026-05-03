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
- [ ] `tiers.py`：L1→L2→L3 邏輯與閾值
- [ ] `health_check()` 回建議
- [ ] 用 fast-forward 時鐘做測試
- [ ] commit：`feat: tiered storage`

### 五 — 向量層（選做）
- [ ] 用 `sentence-transformers` 或 `ollama` 加 bge-m3
- [ ] RRF 合併 BM25 + 向量
- [ ] 來不及就推到週末
- [ ] commit：`feat: hybrid search with vector`

### 六 — 範例 + 自用
- [ ] `examples/01_basic_usage.py` — 30 秒能跑完
- [ ] 在假資料上跑（Wikipedia 100 篇）
- [ ] 截圖 CLI 輸出供 README 用
- [ ] commit：`docs: examples`

### 日 — 公開版 README
- [x] README v0（bootstrap 階段已完成）
- [ ] 加架構圖（Excalidraw 匯出 PNG）
- [ ] 全部 push；**還不要 launch**（Week 2 才發）
- [ ] commit：`docs: v0 README + diagram`

## Week 2：LangChain adapter + benchmark
*(Week 1 結束時詳細規劃)*

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
