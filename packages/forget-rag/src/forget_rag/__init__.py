"""forget-rag — a forgetting layer for RAG systems.

This is the v0.1.0-alpha bootstrap. The public surface (ForgettingMemory)
is declared here so users can `from forget_rag import ForgettingMemory`,
but real behavior lands in subsequent commits per ROADMAP.md.
"""

from __future__ import annotations

__version__ = "0.1.0a0"

__all__ = ["ForgettingMemory", "Chunk", "HealthReport"]


class ForgettingMemory:
    """Stub. See SPEC.md for the v0.1 API surface.

    Real implementation lands incrementally:
        - Tue: SQLite backend + heat scoring
        - Wed: add / search / forget primitives
        - Thu: tier transitions + health_check
    """

    def __init__(self, *args, **kwargs) -> None:
        raise NotImplementedError(
            "forget-rag v0.1.0-alpha is in bootstrap. "
            "See ROADMAP.md for the implementation schedule."
        )


class Chunk:
    """Stub for search results."""


class HealthReport:
    """Stub for health_check() output."""
