"""Heat scoring — exponential decay with access bonus.

Pure functions, no I/O. Easy to reason about and test.

The heat score answers: "how relevant is this chunk *right now*?"
It combines three signals:
    1. Time decay     — older chunks lose heat exponentially
    2. Access bonus   — recently accessed chunks regain heat
    3. Tag weight     — caller can pin certain tags (e.g. "starred")
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import UTC, datetime

# Default tunables. Override per-instance via ForgettingMemory(...).
DEFAULT_HALFLIFE_DAYS = 30.0
DEFAULT_ACCESS_BONUS = 0.05      # heat boost per recent access
DEFAULT_RECENT_WINDOW_DAYS = 7   # only accesses within this window count

LN2 = math.log(2)


@dataclass(frozen=True, slots=True)
class HeatInputs:
    """Snapshot of a chunk's heat-relevant state."""

    base_score: float
    created_at: datetime
    last_access: datetime | None
    access_count: int
    tag_weight: float = 0.0

    def __post_init__(self) -> None:
        if self.base_score < 0:
            raise ValueError("base_score must be >= 0")
        if self.access_count < 0:
            raise ValueError("access_count must be >= 0")


def compute_heat(
    inputs: HeatInputs,
    *,
    now: datetime | None = None,
    halflife_days: float = DEFAULT_HALFLIFE_DAYS,
    access_bonus: float = DEFAULT_ACCESS_BONUS,
    recent_window_days: float = DEFAULT_RECENT_WINDOW_DAYS,
) -> float:
    """Compute current heat score.

    Formula:
        heat = base * exp(-ln(2) * age_days / halflife)
             + access_bonus * recent_accesses
             + tag_weight

    Args:
        inputs: chunk state (base_score, timestamps, access_count, tag_weight).
        now: clock injection point — defaults to UTC now.
        halflife_days: half-life of base_score in days. Must be > 0.
        access_bonus: heat added per recent access.
        recent_window_days: an access counts as "recent" if last_access is
            within this many days of `now`. Outside the window, accesses
            still increment access_count but don't contribute bonus.

    Returns:
        Non-negative float. Higher = hotter.
    """
    if halflife_days <= 0:
        raise ValueError("halflife_days must be > 0")

    now = now or datetime.now(UTC)
    age_days = max(0.0, (now - inputs.created_at).total_seconds() / 86400.0)
    decayed = inputs.base_score * math.exp(-LN2 * age_days / halflife_days)

    bonus = 0.0
    if inputs.last_access is not None and inputs.access_count > 0:
        since_last_access_days = (now - inputs.last_access).total_seconds() / 86400.0
        if 0 <= since_last_access_days <= recent_window_days:
            bonus = access_bonus * inputs.access_count

    return decayed + bonus + inputs.tag_weight


def days_until_threshold(
    current_heat: float,
    threshold: float,
    *,
    halflife_days: float = DEFAULT_HALFLIFE_DAYS,
) -> float | None:
    """Estimate when (in days) heat will fall below `threshold`, no further accesses.

    Useful for the health_check report: 'this chunk drops to L2 in ~12 days'.
    Returns None if already below threshold or threshold <= 0.
    """
    if threshold <= 0 or current_heat <= threshold:
        return None
    # heat * exp(-ln2 * d / hl) = threshold  =>  d = hl * log2(heat / threshold)
    return halflife_days * math.log2(current_heat / threshold)
