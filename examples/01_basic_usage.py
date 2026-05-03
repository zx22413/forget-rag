"""
forget-rag — Basic usage example
forget-rag — 基礎用法範例

Run / 執行：
    uv sync
    uv run python examples/01_basic_usage.py

NOTE: This example targets the v0.1 API surface declared in SPEC.md.
      Real behavior lands progressively per ROADMAP.md (Tue–Sat of Week 1).
      Running this today will raise NotImplementedError — that is expected
      during bootstrap.
"""

from forget_rag import ForgettingMemory


def main() -> None:
    # 1) Init memory with 30-day half-life
    # 1) 用 30 天半衰期建立記憶
    memory = ForgettingMemory(
        backend="sqlite",
        sqlite_path=":memory:",          # in-memory for demo / demo 用記憶體
        decay_halflife_days=30.0,
        tiers={"L1": 100, "L2": 1000, "L3": "unlimited"},
    )

    # 2) Add some chunks
    # 2) 寫入幾筆內容
    chunks = [
        ("Project Alpha kicks off Q1 2026.",     ["project", "alpha"]),
        ("Database migration playbook v3.",       ["devops", "playbook"]),
        ("OKR template Q4 2025 — deprecated.",    ["okr", "stale"]),
        ("How to set up Claude Code MCP server.", ["mcp", "claude"]),
        ("Vendor contact: Vendor Co. — Bob.",     ["contact"]),
    ]
    for text, tags in chunks:
        memory.add(text, tags=tags)

    # 3) Search — heat-aware ranking
    # 3) 搜尋 — 帶熱度加權的排序
    print("=== Search: 'mcp' ===")
    for hit in memory.search("mcp", limit=3):
        print(f"  [{hit.tier}] heat={hit.heat:.2f}  {hit.text}")

    # 4) Health check — what's getting cold?
    # 4) 健康檢查 — 哪些變冷了？
    print("\n=== Health report ===")
    report = memory.health_check()
    print(f"  Suggested forgets: {len(report.suggested_forgets)}")
    for s in report.suggested_forgets[:3]:
        print(f"    - {s.text!r}  (reason: {s.reason})")

    # 5) Commit forgets — user decides
    # 5) 真正忘掉 — 使用者決定
    if report.suggested_forgets:
        ids = [s.id for s in report.suggested_forgets]
        n = memory.forget(ids)
        print(f"\n  Forgot {n} chunks. (soft delete, recoverable for 30 days)")


if __name__ == "__main__":
    main()
