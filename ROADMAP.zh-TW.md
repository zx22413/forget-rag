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
- [x] 全部 push；**還不要 launch**（Week 2 才發）
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
- [x] `docs/benchmark.md`：方法、結果、分析、「證明了什麼 / 沒證明什麼」
- [x] `docs/benchmark.zh-TW.md`：中文鏡像
- [x] README：把 `(coming Week 2)` 換成真連結
- [x] commit：`docs(bench): write-up + readme link`

### 六 — LangChain + Chroma 範例
- [x] `examples/02_langchain_retriever.py`：最小的 retriever 接到 chain
- [x] `examples/03_chroma_with_forget_rag.py`：Chroma 負責向量召回，forget-rag 用 heat 重排
- [x] 雙語 docstring + `.out.txt` transcript 留檔
- [x] commit：`docs: langchain + chroma examples`

### 日 — Buffer / push
- [x] 從乾淨 clone 跑 smoke（`uv sync && pytest && examples`）
- [x] 全部 push
- [x] commit：`chore: week 2 close`

## Week 3：mem-broom CLI

Week 2 末確認的決策：
- CLI 框架：**typer**（FastAPI 同作者，type-hint 自動產 `--help`、配 `rich` 表格漂亮）
- 輸出：**人類可讀預設 + `--json` flag**（給管道/腳本串）
- `restore` 子命令：**不做**，留到 Week 4 / v0.2（schema 已有 `forgotten_at`，但要新加 backend API）

### 一 — Scaffold
- [x] 在 `packages/mem-broom/` 建獨立子包（sibling to forget-rag）
- [x] `pyproject.toml`：依賴 `forget-rag` (workspace)、`typer>=0.12`、`rich>=13`
- [x] entry point：`mem-broom = mem_broom.cli:app`
- [x] `mem_broom/cli.py` typer 骨架（空 app + version flag）
- [x] Smoke test：`mem-broom --help` 跑得起來
- [x] commit：`feat(cli): mem-broom scaffolding`

### 二 — 唯讀指令：stats + health
- [x] `mem-broom stats [--db PATH] [--json]`：chunk 數、tier 分布、最熱/最冷
- [x] `mem-broom health [--db PATH] [--json]`：跑 `health_check()` 列建議遺忘
- [x] `--json` 走 stdout、人類可讀走 `rich.Table`
- [x] 兩個指令的 unit test（用 in-memory DB 跑 typer.testing.CliRunner）
- [x] commit：`feat(cli): stats + health commands`

### 三 — 寫入指令：maintain + forget
- [x] `mem-broom maintain [--db PATH] [--json]`：跑 `maintenance()`、印新 tier 分布
- [x] `mem-broom forget <id>... [--yes] [--db PATH]`：軟刪除，預設要 confirm
- [x] confirmation prompt 用 `typer.confirm`，`--yes` 直接跳過
- [x] 測試：confirm decline 不會刪、`--yes` 真的刪
- [x] commit：`feat(cli): maintain + forget commands`

### 四 — search + add
- [x] `mem-broom search <query> [--limit N] [--db PATH] [--json]`
- [x] `mem-broom add <text> [--tag T]... [--db PATH]`
- [x] `add` 支援 stdin pipe：沒給 `<text>` 就讀 stdin（`cat foo.md | mem-broom add`）
- [x] 測試：pipe 行為 + tag 解析
- [x] commit：`feat(cli): search + add commands`

### 五 — Polish：輸出格式 + 錯誤處理
- [x] 統一 JSON envelope：`{"ok": bool, "data": ..., "error": null}`
- [x] DB 路徑不存在 / namespace 空時的友善錯誤訊息
- [x] `--version` flag、全域 `--namespace` flag
- [x] commit：`feat(cli): json envelope + error messages`

### 六 — 範例 + 文件
- [x] `examples/04_cli_walkthrough.md`：從 add → search → health → forget 一條流程
- [x] README 加 mem-broom 段落（雙語）
- [x] mem-broom 自己的 `packages/mem-broom/README.md`
- [x] commit：`docs: mem-broom cli walkthrough + readme`

### 日 — Buffer / push
- [x] 從乾淨 clone 跑 smoke：`uv sync && pytest && mem-broom --help`
- [x] 全部 push
- [x] commit：`chore: week 3 close`

## Week 4：Launch + write-up

Week 3 末確認的決策：
- **PyPI**：上（佔 `forget-rag` + `mem-broom` 名字，推 v0.1.0 wheel）
- **Launch channel**：Medium 文章（軟發布，v0.1 不發 HN / Reddit）
- **Demo 素材**：asciinema 錄影 + 3–4 張靜態截圖
- 向量層維持推遲到 v0.2

### 一 — PyPI metadata 前置
- [ ] `forget-rag` `pyproject.toml` 補 metadata：description、license、classifiers、keywords、urls
- [ ] `mem-broom` `pyproject.toml` 同步
- [ ] 確認兩個名字在 PyPI 還沒被佔
- [ ] `uv build` 兩包都試包（wheel + sdist）
- [ ] 設好 PyPI trusted publisher（透過 GitHub Actions OIDC）
- [ ] commit：`chore: pypi metadata + build setup`

### 二 — Write-up 上半（英文）
- [ ] 草 `docs/blog/launch.md`：problem → 現有 RAG 為什麼壞 → 三個 primitive → benchmark 數字 → 給誰用 / 不給誰用
- [ ] 引用 `docs/benchmark.md` 數字，不重抄
- [ ] 1500–2500 字，中等深度
- [ ] commit：`docs(blog): launch write-up draft (en)`

### 三 — Write-up 下半 + demo
- [ ] `docs/blog/launch.zh-TW.md` 中文鏡像
- [ ] asciinema 錄一段：`mem-broom` walkthrough（add → search → health → maintain → forget），~60 秒
- [ ] 4 張靜態截圖：CLI stats、CLI health、benchmark 表、架構圖
- [ ] 素材丟 `docs/media/`
- [ ] commit：`docs(blog): zh mirror + demo assets`

### 四 — 社群檔
- [ ] `CONTRIBUTING.md`：dev setup、跑 test、PR 規範
- [ ] `CODE_OF_CONDUCT.md`：用 Contributor Covenant v2.1
- [ ] `.github/ISSUE_TEMPLATE/bug_report.md` + `feature_request.md`
- [ ] `.github/PULL_REQUEST_TEMPLATE.md`
- [ ] `SECURITY.md`：回報管道、支援版本
- [ ] commit：`docs: community files (contributing, coc, templates)`

### 五 — Release v0.1.0
- [ ] `CHANGELOG.md`：scaffold → v0.1.0 全部變更
- [ ] `git tag v0.1.0` + GitHub Release notes（從 CHANGELOG 拉）
- [ ] 透過 GitHub Actions publish：`forget-rag==0.1.0`、`mem-broom==0.1.0`
- [ ] 乾淨環境 smoke：`pip install forget-rag mem-broom` 然後跑 `examples/01_basic_usage.py`
- [ ] commit：`chore: release v0.1.0`（推 tag）

### 六 — Launch
- [ ] Medium 文章 publish（英文優先）
- [ ] 文末附：repo link、benchmark link、example link
- [ ] 盯：GitHub star、issue、Medium clap/response
- [ ] P0 bug 立刻 triage + patch
- [ ] hotfix commit（如果有需要）

### 日 — Retro + v0.2 計畫
- [ ] `docs/retro/v0.1.md`：4 週回顧、哪邊有效/無效、scope cut 決策回顧
- [ ] 草 Week 5+：向量層（bge-m3 + RRF）、`restore` 子命令、用戶回饋項
- [ ] Week 5+ 寫進 ROADMAP（雙語）
- [ ] commit：`docs: v0.1 retro + v0.2 roadmap`

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
