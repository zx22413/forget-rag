"""Tests for friendly error handling.

Read commands (stats / health / search / forget / maintain) should
fail loudly when the DB file is missing rather than silently creating
an empty one. All commands should reject empty namespaces.

In ``--json`` mode the error envelope uses the standard shape:
    {"ok": false, "data": null, "error": "..."}
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from mem_broom.cli import app
from typer.testing import CliRunner

runner = CliRunner()


READ_COMMANDS: list[list[str]] = [
    ["stats"],
    ["health"],
    ["search", "anything"],
    ["maintain"],
    ["forget", "some-id", "--yes"],
]


# --- missing DB ----------------------------------------------------------


@pytest.mark.parametrize("cmd", READ_COMMANDS)
def test_missing_db_human_error(tmp_path: Path, cmd: list[str]) -> None:
    missing = tmp_path / "does-not-exist.db"
    result = runner.invoke(app, [*cmd, "--db", str(missing)])
    assert result.exit_code == 1
    assert "database not found" in result.stdout.lower()
    assert not missing.exists(), "the friendly-error path must not create the DB"


@pytest.mark.parametrize("cmd", READ_COMMANDS)
def test_missing_db_json_envelope(tmp_path: Path, cmd: list[str]) -> None:
    missing = tmp_path / "does-not-exist.db"
    result = runner.invoke(app, [*cmd, "--db", str(missing), "--json"])
    assert result.exit_code == 1
    payload = json.loads(result.stdout)
    assert payload["ok"] is False
    assert payload["data"] is None
    assert "database not found" in payload["error"].lower()


# --- empty namespace -----------------------------------------------------


def test_empty_namespace_human_error(tmp_path: Path) -> None:
    db = tmp_path / "x.db"
    db.touch()  # exists, but namespace check runs first
    result = runner.invoke(
        app, ["stats", "--db", str(db), "--namespace", ""]
    )
    assert result.exit_code == 1
    assert "namespace cannot be empty" in result.stdout.lower()


def test_empty_namespace_on_add(tmp_path: Path) -> None:
    """`add` doesn't require an existing DB but still rejects empty ns."""
    db = tmp_path / "x.db"
    result = runner.invoke(
        app, ["add", "hi", "--db", str(db), "--namespace", "", "--json"]
    )
    assert result.exit_code == 1
    payload = json.loads(result.stdout)
    assert payload["ok"] is False
    assert "namespace" in payload["error"].lower()


# --- version flag (regression) -------------------------------------------


def test_version_flag_prints_and_exits() -> None:
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert "mem-broom" in result.stdout.lower()
