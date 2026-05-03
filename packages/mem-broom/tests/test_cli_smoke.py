"""Smoke tests for the mem-broom CLI entry point."""

from __future__ import annotations

from mem_broom import __version__
from mem_broom.cli import app
from typer.testing import CliRunner

runner = CliRunner()


def test_help_runs() -> None:
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "mem-broom" in result.stdout
    assert "sweep stale chunks" in result.stdout.lower()


def test_version_flag() -> None:
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert __version__ in result.stdout


def test_no_args_shows_help() -> None:
    """Calling `mem-broom` with no args should show help, not crash."""
    result = runner.invoke(app, [])
    assert result.exit_code in (0, 2)  # Typer exits 2 for "show help & quit"
    assert "Usage" in result.stdout or "usage" in result.stdout.lower()
