# Changelog

[English](CHANGELOG.md) | 繁體中文

本檔記錄此專案所有值得注意的變更。

格式遵循 [Keep a Changelog](https://keepachangelog.com/zh-TW/1.1.0/)，
版本規範遵循 [Semantic Versioning](https://semver.org/lang/zh-TW/)。

## [Unreleased]

## [0.1.0] - 2026-05-06

首次公開釋出。為 RAG 系統提供可直接套用的「遺忘層」：SQLite + FTS5 後端、heat 衰減評分、三層儲存、LangChain 整合，外加同捆 CLI。

### Added

#### 核心函式庫 — `forget-rag`

- SQLite + FTS5 儲存後端，支援全文索引
- Heat 分數衰減：指數衰減 + 存取加權 + 標籤權重
- `add()` / `search()` / `forget()` 三個 primitives — `forget()` 是軟刪除（透過 `forgotten_at` 保留歷史）
- L1 / L2 / L3 三層儲存與自動轉移規則
- `health_check()` — 列出可遺忘候選與層級漂移
- BM25 + heat-boost 排序（v0.1 不含 vector 層，延後到 v0.2）

#### LangChain 轉接器

- `ForgettingRetriever` 繼承 `BaseRetriever`
- 同步與非同步版本的 `_get_relevant_documents`
- 回傳完整 metadata 的 `Document`（id、heat、tier、score、tags）
- 選用相依群組 `[langchain]` — 沒裝也能 graceful import

#### Benchmark 工具

- `make_corpus(n, age_distribution, seed)` — 合成、可重現
- `make_query_set(corpus, n, seed)` — 帶 ground-truth id 的查詢集
- `measure(memory, queries)` — latency p50/p95 + Precision@5
- 三組設定：純 BM25、BM25 + heat、BM25 + heat + maintenance
- **結果**：在 10k chunks 下，heat boost 把 Precision@1 從 0% 拉到 32%，延遲增加 <25%。完整分析在 [docs/benchmark.zh-TW.md](docs/benchmark.zh-TW.md)。

#### CLI — `mem-broom`

- `mem-broom stats` — chunk 數量、層級分布、最熱/最冷
- `mem-broom health` — 列出建議遺忘的項目
- `mem-broom maintain` — 跑層級轉移、印出 delta
- `mem-broom forget <id>...` — 軟刪除（預設詢問確認，`--yes` 略過）
- `mem-broom search <query>` — 查詢資料庫
- `mem-broom add <text>` — 新增；支援 stdin pipe（`cat foo.md | mem-broom add`）
- `--json` flag — 統一信封 `{ok, data, error}`
- 全域 `--namespace` 與 `--version` flag
- DB 路徑缺失或 namespace 為空時給友善錯誤訊息

#### Examples

- [`examples/01_basic_usage.py`](examples/01_basic_usage.py) — 30 秒能跑起來
- [`examples/02_langchain_retriever.py`](examples/02_langchain_retriever.py) — chain 中的最小 retriever
- [`examples/03_chroma_with_forget_rag.py`](examples/03_chroma_with_forget_rag.py) — Chroma 做 vector 召回 + forget-rag 用 heat 重排
- [`examples/04_cli_walkthrough.md`](examples/04_cli_walkthrough.md) — CLI 全流程示範

#### 專案基礎建設

- 雙語文件（英文 + 繁體中文）：README、ROADMAP、SPEC、benchmark、architecture
- `CONTRIBUTING.md`、`CODE_OF_CONDUCT.md`（Contributor Covenant 2.1）、`SECURITY.md`
- GitHub issue templates（bug report、feature request）與 PR template
- GitHub Actions CI：push 時跑 pytest
- PyPI Trusted Publisher（OIDC）已設定給 `forget-rag`

### 備註

- **`mem-broom` PyPI publish 延後到 v0.1 之後**。PyPI 的 Pending Trusted Publisher 表單在同一帳號加第二個 publisher 時會 500（多個專案名稱都重現）。upstream 追蹤於 [pypi/warehouse#20006](https://github.com/pypi/warehouse/issues/20006)。v0.1 改以 git install 或 GitHub Release 附件（wheel + sdist）的形式發佈。
- **Vector embedding 層延後到 v0.2**。
- **`mem-broom restore` 延後到 v0.2**。schema 已支援（軟刪除保留 `forgotten_at`），只是後端 API 還沒接出來。

[Unreleased]: https://github.com/zx22413/forget-rag/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/zx22413/forget-rag/releases/tag/v0.1.0
