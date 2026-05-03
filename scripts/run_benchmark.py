"""One-shot benchmark runner.

Runs three configs × three corpus sizes, prints an ASCII table, and
saves raw results to docs/benchmark_data/results.json so the Friday
write-up can quote exact numbers without re-running.

Usage:
    uv run python scripts/run_benchmark.py
    uv run python scripts/run_benchmark.py --sizes 1000 10000 --queries 100

Configs:
    bm25_only   — heat_boost_weight=0, no maintenance
    bm25_heat   — heat_boost_weight=1, no maintenance
    bm25_heat_m — heat_boost_weight=1, maintenance() before search
"""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path

from forget_rag import ForgettingMemory
from forget_rag.benchmark import (
    MeasurementResult,
    format_results_table,
    make_corpus,
    make_query_set,
    measure,
    populate,
)

DEFAULT_SIZES = (1_000, 10_000, 100_000)
DEFAULT_QUERIES = 50
DEFAULT_OUT = Path("docs/benchmark_data/results.json")


def _run_one(
    *,
    config_name: str,
    n_chunks: int,
    n_queries: int,
    heat_weight: float,
    do_maintenance: bool,
    now: datetime,
) -> MeasurementResult:
    corpus = make_corpus(n_chunks, seed=42)
    mem = ForgettingMemory(
        sqlite_path=":memory:",
        heat_boost_weight=heat_weight,
    )
    try:
        ids = populate(mem, corpus, now=now)
        queries = make_query_set(corpus, ids, n_queries=n_queries, seed=7)
        if do_maintenance:
            mem.maintenance(now=now)
        return measure(
            mem,
            queries,
            config_name=config_name,
            n_chunks=n_chunks,
        )
    finally:
        mem.close()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--sizes",
        type=int,
        nargs="+",
        default=DEFAULT_SIZES,
        help="Corpus sizes to benchmark (default: 1000 10000 100000).",
    )
    parser.add_argument(
        "--queries",
        type=int,
        default=DEFAULT_QUERIES,
        help=f"Queries per run (default: {DEFAULT_QUERIES}).",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=DEFAULT_OUT,
        help=f"Where to write JSON results (default: {DEFAULT_OUT}).",
    )
    args = parser.parse_args()

    now = datetime.now(UTC)
    results: list[MeasurementResult] = []

    for size in args.sizes:
        print(f"\n[size={size}]")
        for config_name, heat, maint in (
            ("bm25_only",   0.0, False),
            ("bm25_heat",   1.0, False),
            ("bm25_heat_m", 1.0, True),
        ):
            print(f"  running {config_name} ...", flush=True)
            r = _run_one(
                config_name=config_name,
                n_chunks=size,
                n_queries=args.queries,
                heat_weight=heat,
                do_maintenance=maint,
                now=now,
            )
            results.append(r)

    print("\n" + format_results_table(results))

    args.out.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "generated_at": now.isoformat(),
        "queries_per_run": args.queries,
        "results": [asdict(r) for r in results],
    }
    args.out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"\nRaw results saved to {args.out}")


if __name__ == "__main__":
    main()
