"""
forget-rag — Basic usage example
forget-rag — 基礎用法範例

Run / 執行:
    uv sync
    uv run python examples/01_basic_usage.py

This script demonstrates the four core moves of forget-rag:
    1. add()           — write text + tags into memory
    2. search()        — BM25 + heat-aware ranking
    3. maintenance()   — recompute heat, shuffle tiers
    4. health_check()  — non-destructive forget suggestions
    5. forget()        — soft delete (user decides)

To make tier demotion observable in 30 seconds (without waiting weeks
for real decay), some chunks are inserted with back-dated timestamps.
This is purely a demo trick — production code just calls add().
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from forget_rag import ForgettingMemory


def main() -> None:
    now = datetime.now(UTC)

    memory = ForgettingMemory(
        sqlite_path=":memory:",
        decay_halflife_days=30.0,
        tiers={"L1": 2, "L2": 3, "L3": "unlimited"},
    )

    # 1) Seed memory. Some chunks are back-dated so heat decay is visible
    #    immediately — see module docstring.
    seed = [
        ("Project Alpha kicks off Q1 2026.",      ["project"], 0),
        ("Database migration playbook v3.",        ["devops"],  10),
        ("How to set up Claude Code MCP server.",  ["mcp"],     5),
        ("Vendor contact: Vendor Co. — Bob.",      ["contact"], 60),
        ("OKR template Q4 2025 — deprecated.",     ["okr"],     200),
        ("Old meeting notes from 2024 retro.",     ["notes"],   400),
        ("Ancient PDF I never opened.",            ["misc"],    600),
    ]
    for text, tags, age_days in seed:
        # Use the backend directly to back-date created_at for the demo.
        memory._backend.insert(
            text=text, tags=tags, now=now - timedelta(days=age_days)
        )

    print(f"Seeded {memory.count()} chunks.\n")

    # 2) Search — heat-aware ranking. The MCP chunk should win on 'mcp'
    #    even though other chunks share words like 'set' or 'server'.
    print("=== Search: 'mcp' ===")
    for hit in memory.search("mcp", limit=3, now=now):
        print(f"  [{hit.tier}] heat={hit.heat:.3f}  {hit.text}")

    # 3) Maintenance — assign tiers based on current heat.
    print("\n=== Maintenance ===")
    distribution = memory.maintenance(now=now)
    for tier, count in distribution.items():
        print(f"  {tier}: {count}")

    # 4) Health check — what's getting cold? Non-destructive.
    print("\n=== Health report ===")
    report = memory.health_check(now=now)
    print(f"  Total alive: {report.total}")
    print(f"  Suggested forgets: {len(report.suggested_forgets)}")
    for s in report.suggested_forgets[:5]:
        print(f"    - {s.text!r}")
        print(f"        reason: {s.reason}")
    print(f"  Stale chunks (>90 days idle): {len(report.stale_chunks)}")

    # 5) Forget — user commits.
    if report.suggested_forgets:
        ids = [s.id for s in report.suggested_forgets]
        n = memory.forget(ids)
        print(
            f"\n  Forgot {n} chunks. "
            f"(soft delete; rows still exist in DB until purged)"
        )
        print(f"  Alive after forget: {memory.count()}")

    memory.close()


if __name__ == "__main__":
    main()
