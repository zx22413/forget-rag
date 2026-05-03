"""ForgettingMemory — public API surface.

Wires together backend (storage), heat (decay scoring) and tiers (later).
This module is intentionally thin: it orchestrates, it does not compute.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from types import TracebackType
from typing import Literal

from forget_rag.backends.sqlite import SqliteBackend
from forget_rag.heat import HeatInputs, compute_heat
from forget_rag.tiers import (
    HealthReport,
    build_health_report,
    compute_tier_assignments,
)

# --- defaults -------------------------------------------------------------

DEFAULT_TIERS: dict[str, int | str] = {"L1": 100, "L2": 1000, "L3": "unlimited"}


# --- public DTO -----------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Chunk:
    """One search result — the slice of a row a caller actually needs."""

    id: str
    text: str
    tags: list[str] = field(default_factory=list)
    tier: str = "L1"
    heat: float = 0.0
    score: float = 0.0


# --- main class -----------------------------------------------------------


class ForgettingMemory:
    """A memory store that lets old, unused content fade.

    v0.1 wave 1: SQLite + BM25 + heat boost. Vector layer and other
    backends land in subsequent waves per ROADMAP.md.

    Args:
        backend: storage backend identifier. Only "sqlite" in wave 1.
        sqlite_path: path to the SQLite file, or ":memory:" for ephemeral.
        decay_halflife_days: how fast unused chunks lose heat.
        tiers: tier thresholds; defaults to L1=100, L2=1000, L3=unlimited.
        namespace: logical partition for multi-tenant deployments.
        heat_boost_weight: how much heat contributes to ranking (relative
            to BM25 relevance). 0.0 = pure BM25. Default 1.0 — heat and
            relevance are summed with equal weight.
    """

    def __init__(
        self,
        backend: Literal["sqlite", "langchain", "llamaindex"] = "sqlite",
        sqlite_path: str | Path = "forget_rag.db",
        decay_halflife_days: float = 30.0,
        tiers: dict[str, int | str] | None = None,
        namespace: str = "default",
        heat_boost_weight: float = 1.0,
    ) -> None:
        if backend != "sqlite":
            raise NotImplementedError(
                f"backend={backend!r} is planned for v0.2; only 'sqlite' is "
                "available in v0.1 wave 1."
            )
        if decay_halflife_days <= 0:
            raise ValueError("decay_halflife_days must be > 0")
        if heat_boost_weight < 0:
            raise ValueError("heat_boost_weight must be >= 0")

        self._backend = SqliteBackend(sqlite_path, namespace=namespace)
        self._halflife_days = decay_halflife_days
        self._tiers = dict(tiers) if tiers else dict(DEFAULT_TIERS)
        self._heat_boost_weight = heat_boost_weight
        self.namespace = namespace

    # --- lifecycle --------------------------------------------------------

    def close(self) -> None:
        self._backend.close()

    def __enter__(self) -> ForgettingMemory:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.close()

    # --- public API -------------------------------------------------------

    def add(
        self,
        text: str,
        tags: list[str] | None = None,
        metadata: dict | None = None,
    ) -> str:
        """Insert a new chunk. Returns its id."""
        if not text:
            raise ValueError("text must be non-empty")
        return self._backend.insert(text=text, tags=tags, metadata=metadata)

    def search(
        self,
        query: str,
        limit: int = 5,
        *,
        now: datetime | None = None,
    ) -> list[Chunk]:
        """Return up to `limit` chunks ranked by BM25 + heat boost.

        Side effect: every returned chunk is marked accessed, which feeds
        the access bonus on subsequent searches (the "promotion" signal).

        Args:
            query: FTS5 search expression. Empty query returns [].
            limit: max chunks returned. Internally we pull a wider pool
                so heat re-ranking has room to reorder.
            now: clock injection — useful for tests that fast-forward time.
        """
        if not query:
            return []

        now = now or datetime.now(UTC)
        # Pull more candidates than `limit` so heat re-ranking can promote
        # an older-but-hot chunk over a newer-but-barely-matching one.
        pool_size = max(limit * 4, 20)
        candidates = self._backend.fts_search(query, limit=pool_size)

        ranked: list[tuple[Chunk, float]] = []
        for row, relevance in candidates:
            heat = compute_heat(
                HeatInputs(
                    base_score=row.base_score,
                    created_at=row.created_at,
                    last_access=row.last_access,
                    access_count=row.access_count,
                ),
                now=now,
                halflife_days=self._halflife_days,
            )
            score = relevance + self._heat_boost_weight * heat
            chunk = Chunk(
                id=row.id,
                text=row.text,
                tags=list(row.tags),
                tier=row.tier,
                heat=heat,
                score=score,
            )
            ranked.append((chunk, score))

        ranked.sort(key=lambda x: x[1], reverse=True)
        top = [c for c, _ in ranked[:limit]]

        # Promotion signal — accessing a chunk refreshes its heat.
        for chunk in top:
            self._backend.mark_accessed(chunk.id, now=now)

        return top

    def forget(self, chunk_ids: list[str]) -> int:
        """Soft-delete chunks. Returns rows affected (idempotent)."""
        return self._backend.soft_delete(chunk_ids)

    def count(self) -> int:
        """Number of alive (non-forgotten) chunks in this namespace."""
        return self._backend.count_alive()

    def top_chunks(
        self,
        limit: int = 5,
        *,
        hottest: bool = True,
        now: datetime | None = None,
    ) -> list[Chunk]:
        """Return up to `limit` chunks ranked by current heat.

        No side effects — unlike search(), this does *not* mark chunks as
        accessed. Useful for inspection / dashboards / CLI output.

        Args:
            limit: max chunks returned.
            hottest: True for descending (hottest first), False for coldest.
            now: clock injection — useful for tests that fast-forward time.
        """
        if limit <= 0:
            return []
        now = now or datetime.now(UTC)
        scored: list[tuple[Chunk, float]] = []
        for row in self._backend.iter_alive():
            heat = compute_heat(
                HeatInputs(
                    base_score=row.base_score,
                    created_at=row.created_at,
                    last_access=row.last_access,
                    access_count=row.access_count,
                ),
                now=now,
                halflife_days=self._halflife_days,
            )
            scored.append(
                (
                    Chunk(
                        id=row.id,
                        text=row.text,
                        tags=list(row.tags),
                        tier=row.tier,
                        heat=heat,
                        score=heat,
                    ),
                    heat,
                )
            )
        scored.sort(key=lambda x: x[1], reverse=hottest)
        return [c for c, _ in scored[:limit]]

    # --- maintenance & reporting -----------------------------------------

    def maintenance(self, *, now: datetime | None = None) -> dict[str, int]:
        """Recompute heat for every alive chunk and shuffle tiers.

        Returns the new tier distribution. Idempotent — safe to call
        on a cron, after bulk inserts, or never (search still works,
        tiers just stay stale).
        """
        now = now or datetime.now(UTC)
        rows = list(self._backend.iter_alive())
        assignments = compute_tier_assignments(
            rows,
            tier_capacities=self._tiers,
            halflife_days=self._halflife_days,
            now=now,
        )
        for a in assignments:
            self._backend.set_tier(a.chunk_id, a.tier)

        distribution: dict[str, int] = dict.fromkeys(self._tiers, 0)
        for a in assignments:
            distribution[a.tier] = distribution.get(a.tier, 0) + 1
        return distribution

    def health_check(
        self,
        *,
        now: datetime | None = None,
        stale_after_days: float = 90.0,
        forget_heat_floor: float = 0.05,
    ) -> HealthReport:
        """Return a snapshot of memory health.

        Non-destructive — surfaces *suggestions* only. Acting on them
        (calling forget()) is always the user's decision per design
        principle #3.
        """
        now = now or datetime.now(UTC)
        rows = list(self._backend.iter_alive())
        return build_health_report(
            rows,
            tier_capacities=self._tiers,
            halflife_days=self._halflife_days,
            now=now,
            stale_after_days=stale_after_days,
            forget_heat_floor=forget_heat_floor,
        )
