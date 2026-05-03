"""mem-broom CLI entry point.

Day 1 scaffold: just `--help` and `--version` work. Subcommands land
day by day per ROADMAP Week 3.
"""

from __future__ import annotations

import typer

from mem_broom import __version__

app = typer.Typer(
    name="mem-broom",
    help="CLI broom for forget-rag — sweep stale chunks out of your RAG memory.",
    no_args_is_help=True,
    add_completion=False,
)


def _version_callback(value: bool) -> None:
    if value:
        typer.echo(f"mem-broom {__version__}")
        raise typer.Exit()


@app.callback()
def _main(
    version: bool = typer.Option(
        False,
        "--version",
        callback=_version_callback,
        is_eager=True,
        help="Show version and exit.",
    ),
) -> None:
    """Root callback. Subcommands are registered as `app.command()` below."""


if __name__ == "__main__":
    app()
