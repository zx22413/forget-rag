"""Storage backends for forget-rag.

Each backend exposes a CRUD + search interface; heat scoring and tier
transitions live in the upper layers and are backend-agnostic.
"""

from __future__ import annotations

from forget_rag.backends.sqlite import ChunkRow, SqliteBackend

__all__ = ["ChunkRow", "SqliteBackend"]
