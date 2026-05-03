# Security Policy

## Supported versions

forget-rag is in early alpha. Only the latest minor release (currently
v0.1.x) receives security fixes. Older releases will not be patched —
please upgrade.

| Version | Supported          |
|---------|--------------------|
| 0.1.x   | ✅                 |
| < 0.1   | ❌                 |

## Reporting a vulnerability

**Please do not open a public GitHub issue for security vulnerabilities.**

Instead, open a private security advisory:

**https://github.com/zx22413/forget-rag/security/advisories/new**

Include:

- A description of the issue
- The version of forget-rag (or commit SHA) where you saw it
- Reproduction steps or proof-of-concept code
- Impact assessment (what an attacker could do)

You'll get an acknowledgement within 7 days. If the issue is confirmed,
the maintainer will work with you on a coordinated disclosure timeline
(typically 30–90 days, depending on severity).

## Scope

The following are in-scope for security reports:

- The `forget-rag` Python library (`packages/forget-rag/`)
- The `mem-broom` CLI (`packages/mem-broom/`)
- The published PyPI packages (`forget-rag`, `mem-broom`)
- The CI/CD configuration in `.github/workflows/`

The following are **not** in-scope:

- Third-party dependencies (report directly to those projects)
- Issues that require local filesystem or shell access (this is a
  developer tool — local trust is assumed)
- Denial-of-service via crafted SQLite inputs against your own database
  (you control the input)

## What counts as a vulnerability

For a developer-facing tool like this, the realistic threat model is
narrow. Examples we'd want to know about:

- Code execution from a crafted query string or chunk content
- Path traversal via the `--db PATH` argument
- SQL injection in any internal query construction
- Secrets accidentally logged or leaked into stack traces
