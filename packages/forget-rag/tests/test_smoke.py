"""Smoke test: verify the package imports and version is set."""

from __future__ import annotations

import forget_rag


def test_version_set() -> None:
    assert forget_rag.__version__.startswith("0.1.0")


def test_public_api_exposed() -> None:
    assert hasattr(forget_rag, "ForgettingMemory")
    assert hasattr(forget_rag, "Chunk")


def test_can_instantiate_in_memory() -> None:
    """Real impl available — :memory: backend should work without IO."""
    mem = forget_rag.ForgettingMemory(sqlite_path=":memory:")
    try:
        assert mem.count() == 0
    finally:
        mem.close()
