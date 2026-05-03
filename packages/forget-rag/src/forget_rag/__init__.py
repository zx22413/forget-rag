"""forget-rag — a forgetting layer for RAG systems.

Public surface:
    >>> from forget_rag import ForgettingMemory, Chunk

See SPEC.md for the v0.1 API contract and ROADMAP.md for what's wired
in each release.
"""

from __future__ import annotations

from forget_rag.memory import Chunk, ForgettingMemory
from forget_rag.tiers import (
    ForgetSuggestion,
    HealthReport,
    StaleChunk,
    TierAssignment,
)

__version__ = "0.1.0a2"

__all__ = [
    "Chunk",
    "ForgetSuggestion",
    "ForgettingMemory",
    "HealthReport",
    "StaleChunk",
    "TierAssignment",
]
