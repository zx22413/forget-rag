<!--
Thanks for the PR! A few notes before you submit:

- One concept per PR. Don't bundle a fix with a refactor.
- Conventional commit prefix in the title: feat / fix / docs / test
  / chore / refactor / perf / ci.
- Tests are required for new features and bug fixes.
- CI must be green (pytest + ruff). Run locally first:
    uv run ruff check . && uv run pytest
-->

## What this changes

A short description of what this PR does. Not how — the diff shows how.

## Why

The motivation. Link to a GitHub issue if there is one (`Closes #N`).
For features, this is also the right place to argue scope: why does
this belong in forget-rag rather than as a separate tool or downstream
adapter?

## How to verify

```bash
# the exact commands a reviewer should run
```

## Checklist

- [ ] One concept per PR (no bundled changes)
- [ ] Tests added or updated
- [ ] `uv run ruff check .` passes locally
- [ ] `uv run pytest` passes locally
- [ ] No real Brain / Claude Code memory data in tests or examples
- [ ] If user-facing: README or `examples/` updated
- [ ] If on the ROADMAP: corresponding checkbox ticked
