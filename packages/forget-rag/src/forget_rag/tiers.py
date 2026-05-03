"""Tier transitions and health reporting.

Capacity-based tiering: rank every alive chunk by current heat, then
fill tiers in declared order — top L1_cap → L1, next L2_cap → L2,
remainder → L3 (typically "unlimited"). The tier dict's iteration
order *is* the demotion ladder, so callers control the ordering by
how they construct it.

Pure functions — no I/O, no clock side effects. Memory.maintenance()
calls into here with rows from the backend and applies the result.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from forget_rag.backends.sqlite import ChunkRow
from forget_rag.heat import HeatInputs, compute_heat

# --- types ---------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class TierAssignment:
    """Where a chunk should live after the next maintenance pass."""

    chunk_id: str
    tier: str
    heat: float
    rank: int  # 1-based, within-tier rank by heat (1 = hottest in tier)


@dataclass(frozen=True, slots=True)
class ForgetSuggestion:
    id: str
    text: str
    reason: str
    heat: float


@dataclass(frozen=True, slots=True)
class StaleChunk:
    id: str
    text: str
    last_access: datetime | None
    days_since_access: float


@dataclass(frozen=True, slots=True)
class HealthReport:
    """Snapshot of memory health, surfaced via ForgettingMemory.health_check()."""

    total: int
    tier_distribution: dict[str, int]
    suggested_forgets: list[ForgetSuggestion]
    stale_chunks: list[StaleChunk]


# --- capacity parsing ----------------------------------------------------

_UNLIMITED_SENTINELS = frozenset({"unlimited", "*", "inf", "infinity"})


def _parse_capacity(value: int | str) -> int | None:
    """Return an int cap, or None for unlimited."""
    if isinstance(value, int):
        if value < 0:
            raise ValueError(f"tier capacity must be >= 0, got {value}")
        return value
    if isinstance(value, str) and value.strip().lower() in _UNLIMITED_SENTINELS:
        return None
    raise ValueError(f"unrecognised tier capacity: {value!r}")


# --- assignment ----------------------------------------------------------


def compute_tier_assignments(
    rows: list[ChunkRow],
    *,
    tier_capacities: dict[str, int | str],
    halflife_days: float,
    now: datetime,
) -> list[TierAssignment]:
    """Bin rows into tiers by current heat.

    Iteration order of `tier_capacities` *is* the demotion ladder.
    Capacity values are either ints (max chunks in that tier) or the
    string "unlimited".

    Args:
        rows: alive chunks (caller filters out forgotten).
        tier_capacities: e.g. {"L1": 100, "L2": 1000, "L3": "unlimited"}.
        halflife_days: forwarded to compute_heat.
        now: clock injection point.

    Returns:
        One TierAssignment per row. Caller applies via backend.set_tier.
    """
    if not tier_capacities:
        raise ValueError("tier_capacities must be non-empty")

    scored = [
        (
            row,
            compute_heat(
                HeatInputs(
                    base_score=row.base_score,
                    created_at=row.created_at,
                    last_access=row.last_access,
                    access_count=row.access_count,
                ),
                now=now,
                halflife_days=halflife_days,
            ),
        )
        for row in rows
    ]
    scored.sort(key=lambda x: x[1], reverse=True)

    assignments: list[TierAssignment] = []
    cursor = 0
    n = len(scored)

    for tier_name, raw_cap in tier_capacities.items():
        cap = _parse_capacity(raw_cap)
        end = n if cap is None else min(cursor + cap, n)
        for rank, (row, heat) in enumerate(scored[cursor:end], start=1):
            assignments.append(
                TierAssignment(
                    chunk_id=row.id, tier=tier_name, heat=heat, rank=rank
                )
            )
        cursor = end
        if cursor >= n:
            break

    # Anything left after every tier ran out of capacity stays in its
    # current tier (probably L3) — we don't invent new tiers.
    return assignments


# --- health report -------------------------------------------------------


def build_health_report(
    rows: list[ChunkRow],
    *,
    tier_capacities: dict[str, int | str],
    halflife_days: float,
    now: datetime,
    stale_after_days: float = 90.0,
    forget_heat_floor: float = 0.05,
    suggested_forgets_limit: int = 20,
) -> HealthReport:
    """Build a HealthReport from the current alive rows.

    Suggestions are non-destructive — `forget()` is a separate, explicit
    user action per design principle #3 (never auto-deletes).

    Args:
        rows: alive chunks.
        tier_capacities, halflife_days, now: same as compute_tier_assignments.
        stale_after_days: a chunk is "stale" if its last access (or
            creation, if never accessed) is older than this.
        forget_heat_floor: chunks with heat below this are flagged for
            possible forget. Default 0.05 ≈ five half-lives below base 1.0.
        suggested_forgets_limit: cap on how many forget suggestions to
            return so the report stays scannable.
    """
    assignments = compute_tier_assignments(
        rows,
        tier_capacities=tier_capacities,
        halflife_days=halflife_days,
        now=now,
    )

    by_id: dict[str, ChunkRow] = {r.id: r for r in rows}
    tier_distribution: dict[str, int] = dict.fromkeys(tier_capacities, 0)
    for a in assignments:
        tier_distribution[a.tier] = tier_distribution.get(a.tier, 0) + 1

    cold = [a for a in assignments if a.heat < forget_heat_floor]
    cold.sort(key=lambda a: a.heat)  # coldest first
    suggested_forgets = [
        ForgetSuggestion(
            id=a.chunk_id,
            text=by_id[a.chunk_id].text,
            reason=f"heat {a.heat:.4f} below floor {forget_heat_floor}",
            heat=a.heat,
        )
        for a in cold[:suggested_forgets_limit]
    ]

    stale_chunks: list[StaleChunk] = []
    for row in rows:
        reference_time = row.last_access or row.created_at
        days_idle = (now - reference_time).total_seconds() / 86400.0
        if days_idle > stale_after_days:
            stale_chunks.append(
                StaleChunk(
                    id=row.id,
                    text=row.text,
                    last_access=row.last_access,
                    days_since_access=days_idle,
                )
            )
    stale_chunks.sort(key=lambda s: s.days_since_access, reverse=True)

    return HealthReport(
        total=len(rows),
        tier_distribution=tier_distribution,
        suggested_forgets=suggested_forgets,
        stale_chunks=stale_chunks,
    )
