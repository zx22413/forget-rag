"""mem-broom CLI entry point."""

from __future__ import annotations

from pathlib import Path

import typer
from forget_rag import ForgettingMemory
from rich.table import Table

from mem_broom import __version__
from mem_broom._io import console, emit_json, truncate

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
    version: bool = typer.Option(  # noqa: ARG001 — used via callback
        False,
        "--version",
        callback=_version_callback,
        is_eager=True,
        help="Show version and exit.",
    ),
) -> None:
    """Root callback. Subcommands are registered as `app.command()` below."""


# --- shared option types -------------------------------------------------

DbOption = typer.Option(
    "forget_rag.db",
    "--db",
    help="Path to the SQLite database file.",
)
NamespaceOption = typer.Option(
    "default",
    "--namespace",
    help="Logical namespace within the DB.",
)
HalflifeOption = typer.Option(
    30.0,
    "--halflife",
    help="Heat decay halflife in days.",
)
JsonOption = typer.Option(
    False,
    "--json",
    help="Emit machine-readable JSON instead of human-readable tables.",
)


# --- stats ---------------------------------------------------------------


@app.command()
def stats(
    db: Path = DbOption,
    namespace: str = NamespaceOption,
    halflife: float = HalflifeOption,
    json_out: bool = JsonOption,
) -> None:
    """Show chunk count, tier distribution, and hottest / coldest chunks."""
    with ForgettingMemory(
        sqlite_path=db,
        namespace=namespace,
        decay_halflife_days=halflife,
    ) as mem:
        total = mem.count()
        report = mem.health_check()
        hottest = mem.top_chunks(limit=3, hottest=True)
        coldest = mem.top_chunks(limit=3, hottest=False)

    if json_out:
        emit_json(
            {
                "ok": True,
                "data": {
                    "namespace": namespace,
                    "db": str(db),
                    "total": total,
                    "tier_distribution": report.tier_distribution,
                    "hottest": [
                        {"id": c.id, "heat": c.heat, "tier": c.tier, "text": c.text}
                        for c in hottest
                    ],
                    "coldest": [
                        {"id": c.id, "heat": c.heat, "tier": c.tier, "text": c.text}
                        for c in coldest
                    ],
                },
                "error": None,
            }
        )
        return

    console.print(f"[bold]namespace[/]: {namespace}    [bold]db[/]: {db}")
    console.print(f"[bold]total alive chunks[/]: {total}")

    tier_table = Table(title="Tier distribution", show_header=True)
    tier_table.add_column("Tier")
    tier_table.add_column("Count", justify="right")
    for tier, count in report.tier_distribution.items():
        tier_table.add_row(tier, str(count))
    console.print(tier_table)

    if hottest:
        hot_table = Table(title="Hottest chunks", show_header=True)
        hot_table.add_column("ID")
        hot_table.add_column("Tier")
        hot_table.add_column("Heat", justify="right")
        hot_table.add_column("Text")
        for c in hottest:
            hot_table.add_row(c.id[:12], c.tier, f"{c.heat:.3f}", truncate(c.text))
        console.print(hot_table)

    if coldest:
        cold_table = Table(title="Coldest chunks", show_header=True)
        cold_table.add_column("ID")
        cold_table.add_column("Tier")
        cold_table.add_column("Heat", justify="right")
        cold_table.add_column("Text")
        for c in coldest:
            cold_table.add_row(c.id[:12], c.tier, f"{c.heat:.3f}", truncate(c.text))
        console.print(cold_table)


# --- health --------------------------------------------------------------


@app.command()
def health(
    db: Path = DbOption,
    namespace: str = NamespaceOption,
    halflife: float = HalflifeOption,
    stale_after_days: float = typer.Option(
        90.0,
        "--stale-after-days",
        help="A chunk is 'stale' if untouched for this many days.",
    ),
    forget_heat_floor: float = typer.Option(
        0.05,
        "--forget-heat-floor",
        help="Suggest forgetting chunks whose heat falls below this threshold.",
    ),
    json_out: bool = JsonOption,
) -> None:
    """Run health_check() — list suggested forgets and stale chunks."""
    with ForgettingMemory(
        sqlite_path=db,
        namespace=namespace,
        decay_halflife_days=halflife,
    ) as mem:
        report = mem.health_check(
            stale_after_days=stale_after_days,
            forget_heat_floor=forget_heat_floor,
        )

    if json_out:
        emit_json(
            {
                "ok": True,
                "data": {
                    "namespace": namespace,
                    "db": str(db),
                    "total": report.total,
                    "tier_distribution": report.tier_distribution,
                    "suggested_forgets": [
                        {"id": s.id, "heat": s.heat, "reason": s.reason, "text": s.text}
                        for s in report.suggested_forgets
                    ],
                    "stale_chunks": [
                        {
                            "id": s.id,
                            "days_since_access": s.days_since_access,
                            "text": s.text,
                        }
                        for s in report.stale_chunks
                    ],
                },
                "error": None,
            }
        )
        return

    console.print(
        f"[bold]Health check[/] — namespace=[cyan]{namespace}[/] db=[cyan]{db}[/]"
    )
    console.print(f"Total alive: [bold]{report.total}[/]")

    if report.suggested_forgets:
        forget_table = Table(title="Suggested forgets", show_header=True)
        forget_table.add_column("ID")
        forget_table.add_column("Heat", justify="right")
        forget_table.add_column("Reason")
        forget_table.add_column("Text")
        for s in report.suggested_forgets:
            forget_table.add_row(s.id[:12], f"{s.heat:.3f}", s.reason, truncate(s.text))
        console.print(forget_table)
    else:
        console.print("[green]No forget suggestions.[/]")

    if report.stale_chunks:
        stale_table = Table(title="Stale chunks", show_header=True)
        stale_table.add_column("ID")
        stale_table.add_column("Days since access", justify="right")
        stale_table.add_column("Text")
        for s in report.stale_chunks:
            stale_table.add_row(s.id[:12], f"{s.days_since_access:.1f}", truncate(s.text))
        console.print(stale_table)
    else:
        console.print("[green]No stale chunks.[/]")


# --- maintain ------------------------------------------------------------


@app.command()
def maintain(
    db: Path = DbOption,
    namespace: str = NamespaceOption,
    halflife: float = HalflifeOption,
    json_out: bool = JsonOption,
) -> None:
    """Run maintenance(): recompute heat and reshuffle tier assignments."""
    with ForgettingMemory(
        sqlite_path=db,
        namespace=namespace,
        decay_halflife_days=halflife,
    ) as mem:
        distribution = mem.maintenance()
        total = mem.count()

    if json_out:
        emit_json(
            {
                "ok": True,
                "data": {
                    "namespace": namespace,
                    "db": str(db),
                    "total": total,
                    "tier_distribution": distribution,
                },
                "error": None,
            }
        )
        return

    console.print(
        f"[bold]Maintenance run[/] — namespace=[cyan]{namespace}[/] db=[cyan]{db}[/]"
    )
    console.print(f"Total alive: [bold]{total}[/]")

    tier_table = Table(title="New tier distribution", show_header=True)
    tier_table.add_column("Tier")
    tier_table.add_column("Count", justify="right")
    for tier, count in distribution.items():
        tier_table.add_row(tier, str(count))
    console.print(tier_table)


# --- forget --------------------------------------------------------------


@app.command()
def forget(
    chunk_ids: list[str] = typer.Argument(
        ...,
        metavar="ID...",
        help="One or more chunk ids to soft-delete.",
    ),
    db: Path = DbOption,
    namespace: str = NamespaceOption,
    yes: bool = typer.Option(
        False,
        "--yes",
        "-y",
        help="Skip confirmation prompt.",
    ),
    json_out: bool = JsonOption,
) -> None:
    """Soft-delete chunks by id. Prompts for confirmation unless --yes."""
    if not chunk_ids:
        raise typer.BadParameter("at least one ID is required")

    if not yes:
        preview = ", ".join(cid[:12] for cid in chunk_ids)
        confirmed = typer.confirm(
            f"Forget {len(chunk_ids)} chunk(s) [{preview}] in namespace "
            f"'{namespace}'?",
            default=False,
        )
        if not confirmed:
            if json_out:
                emit_json(
                    {
                        "ok": False,
                        "data": {"forgotten": 0, "ids": list(chunk_ids)},
                        "error": "aborted by user",
                    }
                )
            else:
                console.print("[yellow]Aborted — nothing forgotten.[/]")
            raise typer.Exit(code=1)

    with ForgettingMemory(
        sqlite_path=db,
        namespace=namespace,
    ) as mem:
        affected = mem.forget(list(chunk_ids))

    if json_out:
        emit_json(
            {
                "ok": True,
                "data": {
                    "namespace": namespace,
                    "db": str(db),
                    "requested": len(chunk_ids),
                    "forgotten": affected,
                    "ids": list(chunk_ids),
                },
                "error": None,
            }
        )
        return

    console.print(
        f"[green]Forgotten {affected} of {len(chunk_ids)} requested chunk(s).[/]"
    )


if __name__ == "__main__":
    app()
