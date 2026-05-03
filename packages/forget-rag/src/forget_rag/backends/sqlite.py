"""SQLite + FTS5 storage backend.

Pure storage layer: schema, CRUD, BM25 search. No heat scoring, no tier
transitions — those live in upper layers and operate on rows returned
from here. Keeping this thin makes it easy to swap for LangChain /
LlamaIndex adapters later.

Schema follows SPEC.md exactly (chunks + chunks_fts). The chunks_vec
table is intentionally omitted in v0.1 wave 1; the vector layer lands
later and will add it via `CREATE TABLE IF NOT EXISTS`.
"""

from __future__ import annotations

import json
import sqlite3
import uuid
from collections.abc import Iterable, Iterator
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from types import TracebackType

# --- schema ---------------------------------------------------------------

# External-content FTS5 table is kept in sync via triggers, per the SQLite
# FTS5 docs ("External Content Tables"). The 'unicode61' tokenizer with
# diacritic removal handles English + most Latin-script languages well;
# we can add a CJK tokenizer later if needed.
SCHEMA = """
CREATE TABLE IF NOT EXISTS chunks (
    id TEXT PRIMARY KEY,
    namespace TEXT NOT NULL DEFAULT 'default',
    text TEXT NOT NULL,
    tags TEXT,
    metadata TEXT,
    tier TEXT NOT NULL DEFAULT 'L1',
    base_score REAL NOT NULL DEFAULT 1.0,
    last_access TEXT,
    access_count INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    forgotten_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_chunks_namespace ON chunks(namespace);
CREATE INDEX IF NOT EXISTS idx_chunks_tier ON chunks(tier);
CREATE INDEX IF NOT EXISTS idx_chunks_forgotten ON chunks(forgotten_at);

CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5(
    text, tags,
    content='chunks',
    content_rowid='rowid',
    tokenize='unicode61 remove_diacritics 2'
);

CREATE TRIGGER IF NOT EXISTS chunks_ai AFTER INSERT ON chunks BEGIN
    INSERT INTO chunks_fts(rowid, text, tags)
        VALUES (new.rowid, new.text, new.tags);
END;

CREATE TRIGGER IF NOT EXISTS chunks_ad AFTER DELETE ON chunks BEGIN
    INSERT INTO chunks_fts(chunks_fts, rowid, text, tags)
        VALUES('delete', old.rowid, old.text, old.tags);
END;

CREATE TRIGGER IF NOT EXISTS chunks_au AFTER UPDATE ON chunks BEGIN
    INSERT INTO chunks_fts(chunks_fts, rowid, text, tags)
        VALUES('delete', old.rowid, old.text, old.tags);
    INSERT INTO chunks_fts(rowid, text, tags)
        VALUES (new.rowid, new.text, new.tags);
END;
"""


# --- row dataclass --------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ChunkRow:
    """One row from the chunks table — pure data, no behavior.

    Frozen so callers can't accidentally mutate a row read from the DB
    and expect the change to persist.
    """

    id: str
    namespace: str
    text: str
    tags: list[str] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)
    tier: str = "L1"
    base_score: float = 1.0
    last_access: datetime | None = None
    access_count: int = 0
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    forgotten_at: datetime | None = None


# --- helpers --------------------------------------------------------------


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _to_iso(dt: datetime | None) -> str | None:
    return dt.isoformat() if dt else None


def _from_iso(s: str | None) -> datetime | None:
    return datetime.fromisoformat(s) if s else None


def _row_to_chunk(row: sqlite3.Row) -> ChunkRow:
    return ChunkRow(
        id=row["id"],
        namespace=row["namespace"],
        text=row["text"],
        tags=json.loads(row["tags"]) if row["tags"] else [],
        metadata=json.loads(row["metadata"]) if row["metadata"] else {},
        tier=row["tier"],
        base_score=row["base_score"],
        last_access=_from_iso(row["last_access"]),
        access_count=row["access_count"],
        created_at=_from_iso(row["created_at"]) or _utc_now(),
        forgotten_at=_from_iso(row["forgotten_at"]),
    )


# --- backend --------------------------------------------------------------


class SqliteBackend:
    """SQLite + FTS5 storage. Single-namespace per instance.

    Connection is held for the lifetime of the instance. Use as a context
    manager or call `close()` explicitly.

    Args:
        path: filesystem path or ":memory:" for an ephemeral DB.
        namespace: logical partition; rows are scoped to this namespace
            and never bleed across instances.
    """

    def __init__(
        self,
        path: str | Path = ":memory:",
        *,
        namespace: str = "default",
    ) -> None:
        self.path = str(path)
        self.namespace = namespace
        # Autocommit mode (isolation_level=None) — each statement commits
        # immediately, which is what we want for a write-light workload.
        # check_same_thread=False so the LangChain adapter can call this
        # backend from BaseRetriever's async executor (different thread).
        # Safe because SQLite itself is thread-safe in its default build
        # and we never issue concurrent statements on this connection —
        # the async path awaits each call serially.
        self._conn = sqlite3.connect(
            self.path, isolation_level=None, check_same_thread=False
        )
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(SCHEMA)

    # --- lifecycle --------------------------------------------------------

    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> SqliteBackend:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.close()

    # --- writes -----------------------------------------------------------

    def insert(
        self,
        text: str,
        *,
        tags: list[str] | None = None,
        metadata: dict | None = None,
        base_score: float = 1.0,
        chunk_id: str | None = None,
        now: datetime | None = None,
    ) -> str:
        """Insert a new chunk. Returns the chunk id."""
        chunk_id = chunk_id or uuid.uuid4().hex
        ts = _to_iso(now or _utc_now())
        self._conn.execute(
            """
            INSERT INTO chunks (id, namespace, text, tags, metadata,
                                base_score, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                chunk_id,
                self.namespace,
                text,
                json.dumps(tags or []),
                json.dumps(metadata or {}),
                base_score,
                ts,
            ),
        )
        return chunk_id

    def mark_accessed(self, chunk_id: str, *, now: datetime | None = None) -> None:
        """Bump access_count and refresh last_access."""
        ts = _to_iso(now or _utc_now())
        self._conn.execute(
            """
            UPDATE chunks
               SET last_access = ?, access_count = access_count + 1
             WHERE id = ? AND namespace = ?
            """,
            (ts, chunk_id, self.namespace),
        )

    def soft_delete(
        self,
        chunk_ids: Iterable[str],
        *,
        now: datetime | None = None,
    ) -> int:
        """Mark chunks as forgotten. Returns rows affected.

        Idempotent: rows already forgotten are left untouched.
        """
        ts = _to_iso(now or _utc_now())
        ids = list(chunk_ids)
        if not ids:
            return 0
        placeholders = ",".join("?" * len(ids))
        cur = self._conn.execute(
            f"""
            UPDATE chunks SET forgotten_at = ?
             WHERE forgotten_at IS NULL
               AND namespace = ?
               AND id IN ({placeholders})
            """,
            (ts, self.namespace, *ids),
        )
        return cur.rowcount

    def set_tier(self, chunk_id: str, tier: str) -> None:
        self._conn.execute(
            "UPDATE chunks SET tier = ? WHERE id = ? AND namespace = ?",
            (tier, chunk_id, self.namespace),
        )

    # --- reads ------------------------------------------------------------

    def get(self, chunk_id: str) -> ChunkRow | None:
        cur = self._conn.execute(
            "SELECT * FROM chunks WHERE id = ? AND namespace = ?",
            (chunk_id, self.namespace),
        )
        row = cur.fetchone()
        return _row_to_chunk(row) if row else None

    def iter_alive(self) -> Iterator[ChunkRow]:
        """Yield every non-forgotten chunk in this namespace."""
        cur = self._conn.execute(
            "SELECT * FROM chunks WHERE namespace = ? AND forgotten_at IS NULL",
            (self.namespace,),
        )
        for row in cur:
            yield _row_to_chunk(row)

    def fts_search(
        self,
        query: str,
        *,
        limit: int = 50,
    ) -> list[tuple[ChunkRow, float]]:
        """BM25 search. Returns (chunk, relevance) sorted best-first.

        SQLite's bm25() returns a *negative* real number where smaller
        (more negative) = better match. We flip the sign so callers see
        a positive "relevance" value where larger = better, which makes
        combining with heat (also larger=better) trivial.
        """
        cur = self._conn.execute(
            """
            SELECT c.*, bm25(chunks_fts) AS bm25_score
              FROM chunks_fts
              JOIN chunks c ON c.rowid = chunks_fts.rowid
             WHERE chunks_fts MATCH ?
               AND c.namespace = ?
               AND c.forgotten_at IS NULL
             ORDER BY bm25_score
             LIMIT ?
            """,
            (query, self.namespace, limit),
        )
        out: list[tuple[ChunkRow, float]] = []
        for row in cur:
            out.append((_row_to_chunk(row), -row["bm25_score"]))
        return out

    def count_alive(self) -> int:
        cur = self._conn.execute(
            "SELECT COUNT(*) FROM chunks WHERE namespace = ? AND forgotten_at IS NULL",
            (self.namespace,),
        )
        return cur.fetchone()[0]
