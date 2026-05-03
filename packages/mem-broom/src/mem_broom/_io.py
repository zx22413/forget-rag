"""Shared helpers for CLI output formatting.

Two output paths:
- Human-readable (default): rich tables on stderr-or-stdout console.
- JSON (--json): a single JSON object on stdout, no extra noise.
"""

from __future__ import annotations

import json
import sys
from typing import Any

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
