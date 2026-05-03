[English](benchmark.md) | [繁體中文](benchmark.zh-TW.md)

# Benchmark — forget-rag v0.1

> **一句話結論。** 在 1 萬筆合成 corpus 上，加上 heat 衰減把 Precision@1
> 從 **0% 拉到 32%**，延遲只多了 **<25%**。
> 1 千筆規模時拉幅是 **5.4 倍**（11% → 59%）。10 萬筆時兩種設定都掉到
> 0% — 不是 heat 沒效，是 v0.1 search 候選池太小成為瓶頸。詳見
> [Caveats](#caveats)。

## 設定

| 變數 | 值 |
|------|----|
| Backend | SQLite + FTS5（in-memory） |
| Corpus | 合成、10 個 topic、固定 seed |
| 年齡分佈 | 20% fresh（0–7 天）/ 30% warm（8–90 天）/ 50% cold（91–730 天） |
| Queries | 每組跑 100 個 topic 名稱 query，固定 seed |
| Ground truth | 每個 topic **最新的 3 筆 chunks** 為「相關」 |
| 硬體 | 本機筆電、單核、無暖機 |

Corpus 生成器（`forget_rag.benchmark`）讓同 topic 的每筆 chunk 都用同樣的關鍵字，
純 BM25 沒辦法分辨「新版」跟「舊版」 — 這就是 forget-rag 設計來解決的場景。

## 三組設定

| 名稱 | `heat_boost_weight` | 是否呼叫 `maintenance()` |
|------|---------------------|----------------------|
| `bm25_only`    | 0.0 | 否 |
| `bm25_heat`    | 1.0 | 否 |
| `bm25_heat_m`  | 1.0 | 是 |

## 結果

```
config                   n_chunks   n_q   p50 ms   p95 ms   mean ms    P@1    P@5
---------------------------------------------------------------------------------
bm25_only                    1000   100     0.40     0.70      0.44 11.00% 50.00%
bm25_heat                    1000   100     0.40     0.50      0.41 59.00% 59.00%
bm25_heat_m                  1000   100     0.43     0.64      0.45 59.00% 59.00%
bm25_only                   10000   100     1.01     1.76      1.13  0.00%  7.00%
bm25_heat                   10000   100     1.16     1.94      1.25 32.00% 32.00%
bm25_heat_m                 10000   100     1.42     2.61      1.55 32.00% 32.00%
bm25_only                  100000   100     9.44    11.23      9.56  0.00%  0.00%
bm25_heat                  100000   100     9.89    12.43      9.96  0.00%  0.00%
bm25_heat_m                100000   100    12.24    14.86     12.50  0.00%  0.00%
```

原始數據：[`docs/benchmark_data/results.json`](benchmark_data/results.json)。

## 這份數據證明了什麼

- **Heat 對「新鮮度敏感」的指標效果巨大**。純 BM25 在同 topic 內幾乎隨機挑，
  heat-weighted 排名能在 BM25 命中率 0–11% 的規模下，把最新版排到第一名的比率
  拉到 32–59%。
- **延遲呈次線性，heat 帶來的 overhead 不大**。corpus 從 1k 拉到 100k（100 倍），
  p50 只增加 ~25 倍 — FTS5 表現很正常。Heat 重排再加 ~5–25%，跟精準度的
  提升相比可忽略。

## 這份數據沒有證明什麼

- **100k 規模的崩潰是真的**。10 萬筆時每個 topic 約 1 萬筆。`search()` 從
  BM25 拉一個固定大小 `max(limit*4, 20)` 的候選池後再用 heat 重排。當同
  topic 內 BM25 分數幾乎一致時，最新 3 筆幾乎不會落在前 20 名 — heat 沒辦法把
  BM25 沒撈出來的東西排上去。**tier-aware search**（先過濾 L1、空才退）是
  v0.2 候選功能，可以補上這個缺口。
- **`maintenance()` 在 v0.1 不會影響搜尋數字**。Search 直接用 `heat`，沒用
  `tier`。Maintenance 目前只影響 `health_check()` 報告；tier-as-search-filter
  是 v0.2 要追的。
- **合成 corpus 不等於真實 corpus**。Topic 用一模一樣的關鍵字，真實文本有語意
  重疊、錯字、刻意模糊。我們**沒有宣稱**這個數字會直接套用到你的資料 — 只能
  證明「heat 對新鮮度排序確實有效」這個方向是對的。

## 重現方式

```bash
git clone https://github.com/LBDog/forget-rag.git
cd forget-rag
uv sync
uv run python scripts/run_benchmark.py
```

預設：3 種 size × 3 種設定 × 100 queries。要客製：

```bash
uv run python scripts/run_benchmark.py --sizes 5000 50000 --queries 200
```

結果寫到 `docs/benchmark_data/results.json` 跟 stdout。
