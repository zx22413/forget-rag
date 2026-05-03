"""Tests for the `stats` and `health` subcommands.

Each test gets a fresh on-disk SQLite DB inside a tmp_path so the CLI
can open it the same way an end-user would.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from forget_rag import ForgettingMemory
from mem_broom.cli import app
from typer.testing import CliRunner

runner = CliRunner()
NOW = datetime(2026, 5, 3, 12, 0, 0, tzinfo=UTC)


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    """A fresh empty SQLite DB inside tmp_path (file pre-created)."""
    path = tmp_path / "test.db"
    ForgettingMemory(sqlite_path=path).close()
    return path


@pytest.fixture
def populated_db(tmp_path: Path) -> Path:
    """A DB with one fresh chunk and one very stale chunk."""
    path = tmp_path / "populated.db"
    mem = ForgettingMemory(sqlite_path=path, decay_halflife_days=30.0)
    try:
        mem._backend.insert("fresh news today", now=NOW)
        mem._backend.insert("ancient history", now=NOW - timedelta(days=365))
    finally:
        mem.close()
    return path


# --- stats ---------------------------------------------------------------


def test_stats_human_empty_db(db_path: Path) -> None:
    result = runner.invoke(app, ["stats", "--db", str(db_path)])
    assert result.exit_code == 0, result.stdout
    assert "total alive chunks" in result.stdout.lower()
    assert "0" in result.stdout


def test_stats_json_empty_db(db_path: Path) -> None:
    result = runner.invoke(app, ["stats", "--db", str(db_path), "--json"])
    assert result.exit_code == 0, result.stdout
    payload = json.loads(result.stdout)
    assert payload["ok"] is True
    assert payload["error"] is None
    assert payload["data"]["total"] == 0
    assert payload["data"]["hottest"] == []
    assert payload["data"]["coldest"] == []


def test_stats_json_populated(populated_db: Path) -> None:
    result = runner.invoke(app, ["stats", "--db", str(populated_db), "--json"])
    assert result.exit_code == 0, result.stdout
    payload = json.loads(result.stdout)
    data = payload["data"]
    assert data["total"] == 2
    # hottest should put "fresh" before "ancient"
    assert data["hottest"][0]["text"] == "fresh news today"
    assert data["coldest"][0]["text"] == "ancient history"
    # heat strictly decreasing in hottest list
    heats = [c["heat"] for c in data["hottest"]]
    assert heats == sorted(heats, reverse=True)


def test_stats_human_populated_shows_text(populated_db: Path) -> None:
    result = runner.invoke(app, ["stats", "--db", str(populated_db)])
    assert result.exit_code == 0
    assert "fresh news" in result.stdout
    assert "ancient history" in result.stdout


# --- health --------------------------------------------------------------


def test_health_human_empty_db(db_path: Path) -> None:
    result = runner.invoke(app, ["health", "--db", str(db_path)])
    assert result.exit_code == 0, result.stdout
    assert "no forget suggestions" in result.stdout.lower()
    assert "no stale chunks" in result.stdout.lower()


def test_health_json_empty_db(db_path: Path) -> None:
    result = runner.invoke(app, ["health", "--db", str(db_path), "--json"])
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["ok"] is True
    assert payload["data"]["total"] == 0
    assert payload["data"]["suggested_forgets"] == []
    assert payload["data"]["stale_chunks"] == []


def test_health_json_flags_ancient_chunk_for_forgetting(populated_db: Path) -> None:
    result = runner.invoke(
        app,
        ["health", "--db", str(populated_db), "--json", "--forget-heat-floor", "0.5"],
    )
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    suggested_texts = [s["text"] for s in payload["data"]["suggested_forgets"]]
    # halflife=30d, age=365d → heat ≈ 0.0002, well below floor 0.5
    assert "ancient history" in suggested_texts


def test_namespace_isolation(tmp_path: Path) -> None:
    """Chunks in one namespace must not show up in another's stats."""
    path = tmp_path / "ns.db"
    mem_a = ForgettingMemory(sqlite_path=path, namespace="alpha")
    mem_b = ForgettingMemory(sqlite_path=path, namespace="beta")
    try:
        mem_a.add("alpha-only chunk")
        mem_b.add("beta-only chunk")
    finally:
        mem_a.close()
        mem_b.close()

    result = runner.invoke(
        app, ["stats", "--db", str(path), "--namespace", "alpha", "--json"]
    )
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    texts = [c["text"] for c in payload["data"]["hottest"]]
    assert "alpha-only chunk" in texts
    assert "beta-only chunk" not in texts
