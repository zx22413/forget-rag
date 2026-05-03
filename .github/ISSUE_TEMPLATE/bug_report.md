---
name: Bug report
about: Report something that doesn't work as documented
title: "[bug] "
labels: bug
---

## What happened

A short description of what went wrong.

## What you expected

What you expected to happen instead.

## How to reproduce

Minimal steps to trigger the bug:

```python
# or shell commands for the CLI
```

## Environment

- forget-rag version: (e.g. `0.1.0` from `pip show forget-rag`)
- mem-broom version (if relevant): (`mem-broom --version`)
- Python version: (`python --version`)
- OS: (e.g. macOS 14, Ubuntu 24.04, Windows 11)
- Install method: (`pip install`, `uv sync`, source clone)

## Stack trace / output

If there's an error, paste the full traceback. For CLI bugs, paste the
output with `--json` to make it easier to parse:

```
$ mem-broom <command> --json
```

## Additional context

Anything else that might help — related issues, recent config changes,
size of the database, etc.
