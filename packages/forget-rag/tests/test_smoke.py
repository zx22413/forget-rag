"""Smoke test: verify the package imports and version is set."""

import forget_rag


def test_version_set() -> None:
    assert forget_rag.__version__ == "0.1.0a0"


def test_public_api_exposed() -> None:
    assert hasattr(forget_rag, "ForgettingMemory")
    assert hasattr(forget_rag, "Chunk")
    assert hasattr(forget_rag, "HealthReport")


def test_bootstrap_raises() -> None:
    """Until real impl lands, instantiation should fail loudly."""
    import pytest

    with pytest.raises(NotImplementedError, match="bootstrap"):
        forget_rag.ForgettingMemory()
