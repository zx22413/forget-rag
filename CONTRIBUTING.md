# Contributing to forget-rag

Thanks for taking the time to contribute. This is a small alpha-stage
project — issues and small PRs are welcome, but please open an issue
first for anything bigger than a typo or a one-line fix.

## Project layout

```
forget-rag/
├── packages/
│   ├── forget-rag/        # the library (published as `forget-rag` on PyPI)
│   └── mem-broom/         # CLI broom (published as `forget-rag-broom` on PyPI; CLI command is `mem-broom`)
├── docs/                  # benchmark, architecture, blog drafts
├── examples/              # runnable examples
└── ROADMAP.md             # week-by-week plan; the source of truth for scope
```

It's a `uv` workspace — `packages/*` is automatically discovered.

## Local setup

You'll need [uv](https://docs.astral.sh/uv/) installed (Python 3.11+).

```bash
git clone https://github.com/zx22413/forget-rag.git
cd forget-rag
uv sync --all-extras --dev
```

## Running the test suite

```bash
uv run ruff check .
uv run pytest
```

Both must be green before pushing — CI runs the same two commands and
will reject on either failure. The repo has a record of one CI red caused
by skipping ruff locally; don't repeat it.

## Running the CLI locally

```bash
uv run mem-broom --help
uv run mem-broom add "test note" --db /tmp/x.db --tag demo
uv run mem-broom search "test" --db /tmp/x.db
```

Full walkthrough at [examples/04_cli_walkthrough.md](examples/04_cli_walkthrough.md).

## Pull request guidelines

- **One concept per PR.** Don't bundle a bug fix with a refactor with a
  feature.
- **Conventional commit prefixes** in commit messages and PR titles:
  `feat:`, `fix:`, `docs:`, `test:`, `chore:`, `refactor:`, `perf:`, `ci:`.
- **Tests are required** for new features and bug fixes. Add them in
  `packages/<pkg>/tests/`.
- **No real Brain / Claude Code memory data** in any test, example, or
  screenshot. Synthetic only — see `forget_rag.benchmark.make_corpus`.
- **Keep the README runnable.** Anyone cloning the repo should be able
  to `uv sync && uv run python examples/01_basic_usage.py` and see
  output. If your change breaks that contract, update the example.

## Reporting bugs

See [.github/ISSUE_TEMPLATE/bug_report.md](.github/ISSUE_TEMPLATE/bug_report.md).

## Reporting security issues

See [SECURITY.md](SECURITY.md). Don't open a public issue for security
vulnerabilities.

## Code of conduct

By participating, you agree to abide by the
[Code of Conduct](CODE_OF_CONDUCT.md).

## Scope discipline

forget-rag follows a strict weekly ROADMAP. PRs that introduce features
outside the current week's scope (e.g. adding a vector layer when v0.2
is the planned home for it) will be politely deferred. If you want to
work on something not on the ROADMAP, open an issue first to discuss.
