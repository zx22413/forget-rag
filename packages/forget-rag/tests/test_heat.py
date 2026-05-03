"""Tests for heat scoring — three core cases plus invariants."""

from __future__ import annotations

import math
from datetime import UTC, datetime, timedelta

import pytest
from forget_rag.heat import (
    DEFAULT_HALFLIFE_DAYS,
    HeatInputs,
    compute_heat,
    days_until_threshold,
)

NOW = datetime(2026, 5, 3, 12, 0, 0, tzinfo=UTC)


# --- the three cases promised in ROADMAP ----------------------------------


def test_fresh_chunk_keeps_full_base_score() -> None:
    """Case 1 — chunk created `now`, never accessed -> heat ≈ base."""
    inputs = HeatInputs(
        base_score=1.0,
        created_at=NOW,
        last_access=None,
        access_count=0,
    )
    assert compute_heat(inputs, now=NOW) == pytest.approx(1.0)


def test_aged_chunk_decays_to_half_at_one_halflife() -> None:
    """Case 2 — after one half-life, no accesses -> heat ≈ base / 2."""
    inputs = HeatInputs(
        base_score=1.0,
        created_at=NOW - timedelta(days=DEFAULT_HALFLIFE_DAYS),
        last_access=None,
        access_count=0,
    )
    assert compute_heat(inputs, now=NOW) == pytest.approx(0.5, abs=1e-6)


def test_recent_access_boosts_heat_above_pure_decay() -> None:
    """Case 3 — same age as case 2, but with recent accesses -> heat > 0.5."""
    inputs = HeatInputs(
        base_score=1.0,
        created_at=NOW - timedelta(days=DEFAULT_HALFLIFE_DAYS),
        last_access=NOW - timedelta(days=1),
        access_count=10,
    )
    heat = compute_heat(inputs, now=NOW)
    assert heat > 0.5
    assert heat == pytest.approx(0.5 + 10 * 0.05, abs=1e-6)


# --- invariants -----------------------------------------------------------


def test_old_access_does_not_contribute_bonus() -> None:
    """Access outside the recent window -> bonus = 0."""
    inputs = HeatInputs(
        base_score=1.0,
        created_at=NOW - timedelta(days=DEFAULT_HALFLIFE_DAYS),
        last_access=NOW - timedelta(days=60),  # way past 7-day window
        access_count=10,
    )
    heat = compute_heat(inputs, now=NOW)
    assert heat == pytest.approx(0.5, abs=1e-6)


def test_tag_weight_adds_flat_bonus() -> None:
    inputs = HeatInputs(
        base_score=1.0,
        created_at=NOW,
        last_access=None,
        access_count=0,
        tag_weight=0.3,
    )
    assert compute_heat(inputs, now=NOW) == pytest.approx(1.3)


def test_zero_base_score_is_allowed_and_returns_zero() -> None:
    inputs = HeatInputs(
        base_score=0.0,
        created_at=NOW,
        last_access=None,
        access_count=0,
    )
    assert compute_heat(inputs, now=NOW) == pytest.approx(0.0)


@pytest.mark.parametrize("bad_base", [-0.1, -1.0])
def test_negative_base_score_rejected(bad_base: float) -> None:
    with pytest.raises(ValueError, match="base_score"):
        HeatInputs(
            base_score=bad_base,
            created_at=NOW,
            last_access=None,
            access_count=0,
        )


def test_negative_halflife_rejected() -> None:
    inputs = HeatInputs(
        base_score=1.0,
        created_at=NOW,
        last_access=None,
        access_count=0,
    )
    with pytest.raises(ValueError, match="halflife_days"):
        compute_heat(inputs, now=NOW, halflife_days=-1)


# --- helper function ------------------------------------------------------


def test_days_until_threshold_matches_halflife_at_half() -> None:
    """heat=1.0 dropping to 0.5 should take exactly one half-life."""
    days = days_until_threshold(1.0, 0.5, halflife_days=30.0)
    assert days == pytest.approx(30.0, abs=1e-9)


def test_days_until_threshold_returns_none_when_already_cold() -> None:
    assert days_until_threshold(0.3, 0.5) is None


def test_days_until_threshold_returns_none_for_zero_threshold() -> None:
    assert days_until_threshold(1.0, 0.0) is None


# Sanity: decay function shape (older -> colder, monotone)
@pytest.mark.parametrize("days_old", [0, 7, 30, 90, 365])
def test_decay_is_monotonically_non_increasing(days_old: int) -> None:
    inputs = HeatInputs(
        base_score=1.0,
        created_at=NOW - timedelta(days=days_old),
        last_access=None,
        access_count=0,
    )
    heat = compute_heat(inputs, now=NOW)
    expected = math.exp(-math.log(2) * days_old / DEFAULT_HALFLIFE_DAYS)
    assert heat == pytest.approx(expected, abs=1e-6)
