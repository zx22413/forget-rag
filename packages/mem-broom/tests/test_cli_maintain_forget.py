"""Tests for the `maintain` and `forget` subcommands.

`maintain` is a pure write that recomputes tiers; `forget` soft-deletes
chunks and asks for confirmation by default. The test for the prompt
relies on typer.testing.CliRunner's stdin feed.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from forget_rag import ForgettingMemory
from typer.testing import CliRunner

from mem_broom.cli import app

runner = CliRunner()
NOW = datetime(2026, 5, 3, 12, 0, 0, tzinfo=UTC)


@pytest.fixture
def populated_db(tmp_path: Path) -> tuple[Path, list[str]]:
    """A DB with three chunks of varying ages. Returns (path, ids)."""
    path = tmp_path / "populated.db"
    ids: list[str] = []
    mem = ForgettingMemory(sqlite_path=path, decay_halflife_days=30.0)
    try:
        ids.append(mem._backend.insert("fresh news today", now=NOW))
        ids.append(
            mem._backend.insert("middle aged note", now=NOW - timedelta(days=60))
        )
        ids.append(mem._backend.insert("ancient lore", now=NOW - timedelta(days=400)))
    finally:
        mem.close()
    return path, ids


# --- maintain ------------------------------------------------------------


def test_maintain_human_empty_db(tmp_path: Path) -> None:
    db = tmp_path / "empty.db"
    ForgettingMemory(sqlite_path=db).close()
    result = runner.invoke(app, ["maintain", "--db", str(db)])
    assert result.exit_code == 0, result.stdout
    assert "maintenance run" in result.stdout.lower()
    assert "total alive" in result.stdout.lower()
    # Tier rows are printed even when empty.
    assert "L1" in result.stdout


def test_maintain_json_returns_distribution(populated_db: tuple[Path, list[str]]) -> None:
    path, _ = populated_db
    result = runner.invoke(app, ["maintain", "--db", str(path), "--json"])
    assert result.exit_code == 0, result.stdout
    payload = json.loads(result.stdout)
    assert payload["ok"] is True
    assert payload["error"] is None
    data = payload["data"]
    assert data["total"] == 3
    # default tiers L1=100, L2=1000, L3=unlimited — all 3 chunks fit in L1.
    assert sum(data["tier_distribution"].values()) == 3
    assert "L1" in data["tier_distribution"]


# --- forget --------------------------------------------------------------


def test_forget_with_yes_actually_deletes(populated_db: tuple[Path, list[str]]) -> None:
    path, ids = populated_db
    target = ids[0]

    result = runner.invoke(
        app,
        ["forget", target, "--db", str(path), "--yes", "--json"],
    )
    assert result.exit_code == 0, result.stdout
    payload = json.loads(result.stdout)
    assert payload["ok"] is True
    assert payload["data"]["forgotten"] == 1

    mem = ForgettingMemory(sqlite_path=path)
    try:
        assert mem.count() == 2
    finally:
        mem.close()


def test_forget_decline_keeps_chunk(populated_db: tuple[Path, list[str]]) -> None:
    path, ids = populated_db
    target = ids[1]

    # Feed "n\n" to the typer.confirm prompt → user declines.
    result = runner.invoke(
        app,
        ["forget", target, "--db", str(path)],
        input="n\n",
    )
    assert result.exit_code == 1, result.stdout
    assert "aborted" in result.stdout.lower()

    mem = ForgettingMemory(sqlite_path=path)
    try:
        assert mem.count() == 3
    finally:
        mem.close()


def test_forget_accept_via_prompt(populated_db: tuple[Path, list[str]]) -> None:
    path, ids = populated_db
    target = ids[2]

    result = runner.invoke(
        app,
        ["forget", target, "--db", str(path)],
        input="y\n",
    )
    assert result.exit_code == 0, result.stdout
    assert "forgotten 1" in result.stdout.lower()

    mem = ForgettingMemory(sqlite_path=path)
    try:
        assert mem.count() == 2
    finally:
        mem.close()


def test_forget_multiple_ids(populated_db: tuple[Path, list[str]]) -> None:
    path, ids = populated_db
    result = runner.invoke(
        app,
        ["forget", ids[0], ids[1], "--db", str(path), "--yes", "--json"],
    )
    assert result.exit_code == 0, result.stdout
    payload = json.loads(result.stdout)
    assert payload["data"]["forgotten"] == 2
    assert payload["data"]["requested"] == 2

    mem = ForgettingMemory(sqlite_path=path)
    try:
        assert mem.count() == 1
    finally:
        mem.close()


def test_forget_unknown_id_is_idempotent(tmp_path: Path) -> None:
    """soft_delete on an unknown id should report 0 forgotten, not crash."""
    path = tmp_path / "empty.db"
    # Touch the DB so the namespace exists.
    ForgettingMemory(sqlite_path=path).close()

    result = runner.invoke(
        app,
        ["forget", "no-such-id", "--db", str(path), "--yes", "--json"],
    )
    assert result.exit_code == 0, result.stdout
    payload = json.loads(result.stdout)
    assert payload["ok"] is True
    assert payload["data"]["forgotten"] == 0
