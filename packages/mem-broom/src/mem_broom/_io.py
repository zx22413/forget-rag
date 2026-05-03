"""Shared helpers for CLI output formatting.

Two output paths:
- Human-readable (default): rich tables on stderr-or-stdout console.
- JSON (--json): a single JSON object on stdout, no extra noise.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import typer
from rich.console import Console

# Single shared console — rich auto-detects TTY vs piped output.
console = Console()


def emit_json(data: dict[str, Any]) -> None:
    """Print one JSON object to stdout.

    Always uses ``ensure_ascii=False`` so CJK chunk text stays readable.
    """
    sys.stdout.write(json.dumps(data, ensure_ascii=False, indent=2, default=str))
    sys.stdout.write("\n")


def truncate(text: str, max_len: int = 60) -> str:
    """Trim long chunk text for table display."""
    text = text.replace("\n", " ").strip()
    return text if len(text) <= max_len else text[: max_len - 1] + "…"


def die(message: str, *, json_out: bool, exit_code: int = 1) -> None:
    """Print a friendly error and exit with ``exit_code``.

    In JSON mode the error is wrapped in the standard envelope so callers
    can rely on a single output shape.
    """
    if json_out:
        emit_json({"ok": False, "data": None, "error": message})
    else:
        console.print(f"[red]error:[/] {message}")
    raise typer.Exit(code=exit_code)


def ensure_db_exists(db: Path, *, json_out: bool) -> None:
    """Read commands should fail loudly if the DB file is missing.

    ``sqlite3.connect`` happily creates an empty file, which silently
    masks typos like ``--db worng.db`` — every read returns 0 results
    and the user has no idea why.
    """
    if not db.exists():
        die(
            f"database not found at {db}. "
            "Run 'mem-broom add' to create it, or pass --db pointing to an "
            "existing file.",
            json_out=json_out,
        )


def ensure_namespace(namespace: str, *, json_out: bool) -> None:
    """Reject empty namespaces — they would silently match the default."""
    if not namespace.strip():
        die("namespace cannot be empty", json_out=json_out)
