# mem-broom

CLI broom for [forget-rag](https://github.com/zx22413/forget-rag) — sweep
stale chunks out of your RAG memory from the command line.

> **Status:** Week 3 complete. All six subcommands ship with tests and a
> walkthrough doc. Vector layer + `restore` land later per ROADMAP.

## Install

```bash
# v0.1: install from git (PyPI publish deferred — see note below).
pip install "mem-broom @ git+https://github.com/zx22413/forget-rag.git@v0.1.0#subdirectory=packages/mem-broom"

# Or, from a checkout of the workspace:
uv sync                              # installs forget-rag + mem-broom
# or, standalone editable install:
pip install -e packages/mem-broom
```

> **Why git install in v0.1?** The PyPI Pending Trusted Publisher form
> currently returns a 500 error when adding a second pending publisher
> under one account (the issue is independent of the package name). The
> primary `forget-rag` package is on PyPI; `mem-broom` will follow once
> the upstream bug is resolved. Tracking:
> [pypi/warehouse#20006](https://github.com/pypi/warehouse/issues/20006).

## Subcommands

| Command          | Purpose                                              |
|------------------|------------------------------------------------------|
| `add`            | Insert a chunk (argument or stdin pipe).             |
| `search`         | BM25 + heat search, ranked top-N.                    |
| `stats`          | Chunk count, tier distribution, hottest / coldest.   |
| `health`         | Suggest forgets and stale chunks (non-destructive).  |
| `maintain`       | Recompute heat and re-assign tiers.                  |
| `forget`         | Soft-delete chunks by id (confirm by default).       |

Every command supports `--db PATH`, `--namespace NAME`, and `--json` for
machine-readable output.

## Quickstart

```bash
mem-broom --version
mem-broom --help
mem-broom add "first note" --db /tmp/x.db --tag demo
mem-broom search "first" --db /tmp/x.db
```

A full guided tour with all subcommands lives at
[examples/04_cli_walkthrough.md](../../examples/04_cli_walkthrough.md).

## JSON output

Pass `--json` to any command to receive a single envelope on stdout:

```json
{ "ok": true, "data": { ... }, "error": null }
```

Errors share the same shape with `ok=false`, `data=null`, and a human
sentence in `error`.

## Read vs write commands

- **Read commands** (`stats`, `health`, `search`, `forget`, `maintain`)
  refuse to silently create an empty DB. Pass `--db` to an existing file
  or run `mem-broom add` first.
- **`add`** creates the DB if needed — it's the entry point for an
  empty workspace.

## License

MIT, same as forget-rag.
