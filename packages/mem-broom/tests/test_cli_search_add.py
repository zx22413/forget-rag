"""Tests for the `search` and `add` subcommands.

`add` has two interesting modes:
- positional arg: `mem-broom add "some text"`
- stdin pipe: `cat foo.md | mem-broom add` — text comes from stdin

CliRunner.invoke(input=...) feeds stdin, which is the same channel
typer/click read from in the absence of a TEXT argument.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from forget_rag import ForgettingMemory
from mem_broom.cli import app
from typer.testing import CliRunner

runner = CliRunner()


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    """A pre-created SQLite DB inside tmp_path."""
    path = tmp_path / "test.db"
    ForgettingMemory(sqlite_path=path).close()
    return path


# --- add -----------------------------------------------------------------


def test_add_positional_arg_inserts_chunk(db_path: Path) -> None:
    result = runner.invoke(
        app,
        ["add", "hello world", "--db", str(db_path), "--json"],
    )
    assert result.exit_code == 0, result.stdout
    payload = json.loads(result.stdout)
    assert payload["ok"] is True
    chunk_id = payload["data"]["id"]
    assert chunk_id

    mem = ForgettingMemory(sqlite_path=db_path)
    try:
        assert mem.count() == 1
        # round-trip: stored text comes back via search
        hits = mem.search("hello")
        assert len(hits) == 1
        assert hits[0].text == "hello world"
        assert hits[0].id == chunk_id
    finally:
        mem.close()


def test_add_reads_from_stdin_when_text_omitted(db_path: Path) -> None:
    result = runner.invoke(
        app,
        ["add", "--db", str(db_path), "--json"],
        input="piped content from stdin\n",
    )
    assert result.exit_code == 0, result.stdout
    payload = json.loads(result.stdout)
    assert payload["ok"] is True

    mem = ForgettingMemory(sqlite_path=db_path)
    try:
        hits = mem.search("piped")
        assert hits and hits[0].text == "piped content from stdin"
    finally:
        mem.close()


def test_add_empty_input_errors(db_path: Path) -> None:
    """No argument and empty stdin → BadParameter (exit code 2)."""
    result = runner.invoke(
        app,
        ["add", "--db", str(db_path)],
        input="",
    )
    assert result.exit_code != 0


def test_add_parses_multiple_tags(db_path: Path) -> None:
    result = runner.invoke(
        app,
        [
            "add",
            "tagged note",
            "--tag",
            "alpha",
            "--tag",
            "beta",
            "--db",
            str(db_path),
            "--json",
        ],
    )
    assert result.exit_code == 0, result.stdout
    payload = json.loads(result.stdout)
    assert payload["data"]["tags"] == ["alpha", "beta"]

    mem = ForgettingMemory(sqlite_path=db_path)
    try:
        hits = mem.search("tagged")
        assert hits and sorted(hits[0].tags) == ["alpha", "beta"]
    finally:
        mem.close()


def test_add_short_tag_flag(db_path: Path) -> None:
    """`-t` is the short form of `--tag`."""
    result = runner.invoke(
        app,
        ["add", "short flag", "-t", "x", "-t", "y", "--db", str(db_path), "--json"],
    )
    assert result.exit_code == 0, result.stdout
    payload = json.loads(result.stdout)
    assert payload["data"]["tags"] == ["x", "y"]


# --- search --------------------------------------------------------------


def test_search_empty_db_returns_no_matches(db_path: Path) -> None:
    result = runner.invoke(app, ["search", "anything", "--db", str(db_path)])
    assert result.exit_code == 0
    assert "no matches" in result.stdout.lower()


def test_search_json_returns_hits(db_path: Path) -> None:
    mem = ForgettingMemory(sqlite_path=db_path)
    try:
        mem.add("python typer cli")
        mem.add("rust cargo build")
    finally:
        mem.close()

    result = runner.invoke(
        app,
        ["search", "python", "--db", str(db_path), "--json"],
    )
    assert result.exit_code == 0, result.stdout
    payload = json.loads(result.stdout)
    assert payload["ok"] is True
    results = payload["data"]["results"]
    assert len(results) == 1
    assert "python" in results[0]["text"]
    # search result envelope carries score + heat
    assert "score" in results[0]
    assert "heat" in results[0]


def test_search_respects_limit(db_path: Path) -> None:
    mem = ForgettingMemory(sqlite_path=db_path)
    try:
        for i in range(5):
            mem.add(f"note number {i} about typing")
    finally:
        mem.close()

    result = runner.invoke(
        app,
        ["search", "typing", "--db", str(db_path), "--limit", "2", "--json"],
    )
    assert result.exit_code == 0, result.stdout
    payload = json.loads(result.stdout)
    assert len(payload["data"]["results"]) == 2
