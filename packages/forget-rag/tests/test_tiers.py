"""Tests for tier transitions and health reporting.

Uses fast-forwarded clocks (no real-time waits) and synthetic ChunkRows
so we can exercise edge cases without hitting the backend.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from forget_rag.backends.sqlite import ChunkRow
from forget_rag.tiers import (
    HealthReport,
    TierAssignment,
    _parse_capacity,
    build_health_report,
    compute_tier_assignments,
)

NOW = datetime(2026, 5, 3, 12, 0, 0, tzinfo=UTC)
TIERS_SMALL = {"L1": 2, "L2": 3, "L3": "unlimited"}


def _row(
    cid: str,
    *,
    text: str = "x",
    age_days: float = 0.0,
    base_score: float = 1.0,
    accesses: int = 0,
    last_access_days_ago: float | None = None,
    tier: str = "L1",
) -> ChunkRow:
    last = NOW - timedelta(days=last_access_days_ago) if last_access_days_ago else None
    return ChunkRow(
        id=cid,
        namespace="default",
        text=text,
        tags=[],
        metadata={},
        tier=tier,
        base_score=base_score,
        last_access=last,
        access_count=accesses,
        created_at=NOW - timedelta(days=age_days),
        forgotten_at=None,
    )


# --- capacity parsing -----------------------------------------------------


def test_int_capacity_returns_self() -> None:
    assert _parse_capacity(100) == 100
    assert _parse_capacity(0) == 0


@pytest.mark.parametrize("v", ["unlimited", "UNLIMITED", "  inf ", "*", "infinity"])
def test_unlimited_sentinels_return_none(v: str) -> None:
    assert _parse_capacity(v) is None


def test_negative_int_rejected() -> None:
    with pytest.raises(ValueError, match=">= 0"):
        _parse_capacity(-5)


def test_unknown_string_rejected() -> None:
    with pytest.raises(ValueError, match="unrecognised"):
        _parse_capacity("lots")


# --- assignment basics ----------------------------------------------------


def test_empty_rows_returns_empty() -> None:
    assert (
        compute_tier_assignments(
            [], tier_capacities=TIERS_SMALL, halflife_days=30.0, now=NOW
        )
        == []
    )


def test_empty_tier_capacities_rejected() -> None:
    with pytest.raises(ValueError, match="non-empty"):
        compute_tier_assignments([], tier_capacities={}, halflife_days=30.0, now=NOW)


def test_all_chunks_fit_in_l1() -> None:
    rows = [_row(f"id-{i}") for i in range(2)]
    out = compute_tier_assignments(
        rows, tier_capacities=TIERS_SMALL, halflife_days=30.0, now=NOW
    )
    assert {a.tier for a in out} == {"L1"}
    assert len(out) == 2


def test_overflow_demotes_coldest_to_lower_tiers() -> None:
    """7 chunks into L1=2 / L2=3 / L3=unlimited."""
    # Vary age so heat differs deterministically.
    rows = [_row(f"id-{i}", age_days=float(i * 30)) for i in range(7)]
    out = compute_tier_assignments(
        rows, tier_capacities=TIERS_SMALL, halflife_days=30.0, now=NOW
    )

    by_tier: dict[str, list[TierAssignment]] = {}
    for a in out:
        by_tier.setdefault(a.tier, []).append(a)

    assert len(by_tier["L1"]) == 2
    assert len(by_tier["L2"]) == 3
    assert len(by_tier["L3"]) == 2  # the remaining two

    # Hottest (id-0, age 0) goes to L1; coldest (id-6, age 180) to L3.
    assert by_tier["L1"][0].chunk_id == "id-0"
    assert by_tier["L3"][-1].chunk_id == "id-6"


def test_unlimited_l3_absorbs_remainder() -> None:
    rows = [_row(f"id-{i}", age_days=float(i * 10)) for i in range(50)]
    out = compute_tier_assignments(
        rows,
        tier_capacities={"L1": 1, "L2": 1, "L3": "unlimited"},
        halflife_days=30.0,
        now=NOW,
    )
    in_l3 = [a for a in out if a.tier == "L3"]
    assert len(in_l3) == 48


def test_within_tier_rank_is_one_based_by_heat() -> None:
    rows = [_row(f"id-{i}", age_days=float(i * 30)) for i in range(5)]
    out = compute_tier_assignments(
        rows,
        tier_capacities={"L1": 5, "L2": "unlimited"},
        halflife_days=30.0,
        now=NOW,
    )
    in_l1 = [a for a in out if a.tier == "L1"]
    # Sorted by heat desc means oldest (lowest heat) gets last rank.
    assert [a.rank for a in in_l1] == [1, 2, 3, 4, 5]
    assert in_l1[0].chunk_id == "id-0"
    assert in_l1[-1].chunk_id == "id-4"


def test_rows_beyond_capped_tiers_are_dropped_when_no_unlimited() -> None:
    """If every tier has a finite cap and rows exceed the sum, the extras
    are simply omitted from the assignment list — caller handles."""
    rows = [_row(f"id-{i}", age_days=float(i * 10)) for i in range(5)]
    out = compute_tier_assignments(
        rows, tier_capacities={"L1": 1, "L2": 1}, halflife_days=30.0, now=NOW
    )
    assert len(out) == 2  # 3 rows are unassigned


# --- fast-forward clock --------------------------------------------------


def test_fast_forward_demotes_unaccessed_chunks() -> None:
    """A chunk hot at t=0 falls out of L1 after many half-lives."""
    rows = [
        _row("hot", age_days=0.0),
        _row("warm", age_days=30.0),
        _row("cold", age_days=180.0),
    ]
    out = compute_tier_assignments(
        rows,
        tier_capacities={"L1": 1, "L2": 1, "L3": "unlimited"},
        halflife_days=30.0,
        now=NOW,
    )
    assignments = {a.chunk_id: a.tier for a in out}
    assert assignments["hot"] == "L1"
    assert assignments["warm"] == "L2"
    assert assignments["cold"] == "L3"


def test_recent_access_keeps_old_chunk_in_l1() -> None:
    """Old by creation date but recently accessed -> still hot."""
    rows = [
        _row(
            "rescued",
            age_days=180.0,
            accesses=20,
            last_access_days_ago=1.0,
        ),
        _row("fresh", age_days=0.0, base_score=0.1),  # low base, recent
    ]
    out = compute_tier_assignments(
        rows,
        tier_capacities={"L1": 1, "L2": "unlimited"},
        halflife_days=30.0,
        now=NOW,
    )
    by_tier = {a.chunk_id: a.tier for a in out}
    assert by_tier["rescued"] == "L1"
    assert by_tier["fresh"] == "L2"


# --- health report -------------------------------------------------------


def test_health_report_basic_shape() -> None:
    rows = [_row(f"id-{i}", age_days=float(i * 30)) for i in range(5)]
    rep = build_health_report(
        rows,
        tier_capacities={"L1": 2, "L2": 2, "L3": "unlimited"},
        halflife_days=30.0,
        now=NOW,
    )
    assert isinstance(rep, HealthReport)
    assert rep.total == 5
    assert sum(rep.tier_distribution.values()) == 5


def test_health_report_flags_very_cold_chunks_for_forget() -> None:
    """A chunk whose heat falls below floor shows up in suggestions."""
    rows = [
        _row("hot", age_days=0.0),
        _row("ice", age_days=365.0),  # ~12 half-lives, heat ~ 1/4096
    ]
    rep = build_health_report(
        rows,
        tier_capacities={"L1": "unlimited"},
        halflife_days=30.0,
        now=NOW,
        forget_heat_floor=0.05,
    )
    suggested_ids = [s.id for s in rep.suggested_forgets]
    assert "ice" in suggested_ids
    assert "hot" not in suggested_ids


def test_health_report_stale_uses_last_access_when_present() -> None:
    rows = [
        _row("recent", age_days=200.0, last_access_days_ago=10.0),
        _row("abandoned", age_days=200.0, last_access_days_ago=200.0),
    ]
    rep = build_health_report(
        rows,
        tier_capacities={"L1": "unlimited"},
        halflife_days=30.0,
        now=NOW,
        stale_after_days=90.0,
    )
    stale_ids = [s.id for s in rep.stale_chunks]
    assert "abandoned" in stale_ids
    assert "recent" not in stale_ids


def test_health_report_stale_falls_back_to_creation_when_never_accessed() -> None:
    rows = [
        _row("never_touched", age_days=200.0, last_access_days_ago=None),
    ]
    rep = build_health_report(
        rows,
        tier_capacities={"L1": "unlimited"},
        halflife_days=30.0,
        now=NOW,
        stale_after_days=90.0,
    )
    assert [s.id for s in rep.stale_chunks] == ["never_touched"]


def test_suggested_forgets_capped_by_limit() -> None:
    rows = [_row(f"id-{i}", age_days=365.0) for i in range(50)]  # all cold
    rep = build_health_report(
        rows,
        tier_capacities={"L1": "unlimited"},
        halflife_days=30.0,
        now=NOW,
        forget_heat_floor=10.0,  # everyone is below
        suggested_forgets_limit=5,
    )
    assert len(rep.suggested_forgets) == 5
