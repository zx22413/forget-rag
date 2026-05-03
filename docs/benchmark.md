[English](benchmark.md) | [繁體中文](benchmark.zh-TW.md)

# Benchmark — forget-rag v0.1

> **TL;DR.** On a synthetic 10k-chunk corpus, adding heat decay lifts
> Precision@1 from **0% to 32%** with **<25% latency overhead**.
> At 1k chunks the win is **5.4×** (11% → 59%). At 100k both
> configurations drop to 0% — the v0.1 search candidate pool becomes
> the bottleneck, not the heat scoring. See [Caveats](#caveats).

## Setup

| Knob | Value |
|------|-------|
| Backend | SQLite + FTS5 (in-memory) |
| Corpus | Synthetic, 10 topics, deterministic seed |
| Age mix | 20% fresh (0–7d) / 30% warm (8–90d) / 50% cold (91–730d) |
| Queries | 100 topic-name queries per run, fixed seed |
| Ground truth | The **freshest 3 chunks per topic** are "relevant" |
| Hardware | Local laptop, single core, no warmup |

The corpus generator (`forget_rag.benchmark`) builds chunks where every
chunk in a topic shares the same keyword. Pure BM25 has no way to
prefer the freshest version — the situation forget-rag is built for.

## Configs

| Name | `heat_boost_weight` | Calls `maintenance()` |
|------|---------------------|----------------------|
| `bm25_only`    | 0.0 | no  |
| `bm25_heat`    | 1.0 | no  |
| `bm25_heat_m`  | 1.0 | yes |

## Results

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

Raw results: [`docs/benchmark_data/results.json`](benchmark_data/results.json).

## What this proves

- **Heat boost transforms the freshness-sensitive metric.** Where
  pure BM25 picks essentially at random within a topic, heat-weighted
  ranking surfaces the freshest member as the top hit 32–59% of the
  time at scales where BM25 hits 0–11%.
- **Latency is sublinear and the heat overhead is small.** Going from
  1k to 100k chunks (100× growth) inflates p50 by ~25× — well-behaved
  FTS5. Heat re-ranking adds ~5–25% on top, which is negligible
  compared to the precision lift.

## What this doesn't prove

- **The 100k collapse is real.** At 100k there are ~10k chunks per
  topic. `search()` pulls a fixed candidate pool of `max(limit*4, 20)`
  rows from BM25 first, then re-ranks with heat. The freshest 3 are
  almost never inside that 20-row pool when the BM25 scores within a
  topic are essentially uniform — heat can't promote what BM25 didn't
  surface. **Tier-aware search** (filter to L1 first, fall back if
  empty) is on the v0.2 candidate list and would close this gap.
- **`maintenance()` doesn't change search numbers in v0.1.** Search
  uses `heat` directly, not `tier`. Maintenance currently affects only
  what `health_check()` reports; tier-as-search-filter is the v0.2
  follow-up.
- **Synthetic corpus ≠ real corpus.** Topics share verbatim keywords;
  real text has semantic overlap, typos, and intentional ambiguity.
  We don't claim these numbers carry over to your data — only that
  the *direction* (heat helps freshness ranking) is real.

## Reproduce

```bash
git clone https://github.com/LBDog/forget-rag.git
cd forget-rag
uv sync
uv run python scripts/run_benchmark.py
```

Default: 3 sizes × 3 configs × 100 queries. Customize:

```bash
uv run python scripts/run_benchmark.py --sizes 5000 50000 --queries 200
```

Results land in `docs/benchmark_data/results.json` and stdout.
