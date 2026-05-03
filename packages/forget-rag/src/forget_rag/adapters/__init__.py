"""Output adapters that bridge forget-rag into other ecosystems.

Adapters are *optional* — they require their target framework to be
installed. To keep `import forget_rag` cheap and dependency-free, the
adapter classes are loaded lazily via __getattr__. A user who never
touches LangChain never pays the import cost.

Install the LangChain adapter with::

    pip install forget-rag[langchain]
    # or, with uv:
    uv pip install 'forget-rag[langchain]'
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    # For type-checkers and IDEs only — no runtime cost.
    from forget_rag.adapters.langchain import ForgettingRetriever

__all__ = ["ForgettingRetriever"]


def __getattr__(name: str):
    if name == "ForgettingRetriever":
        try:
            from forget_rag.adapters.langchain import ForgettingRetriever
        except ImportError as e:
            raise ImportError(
                "ForgettingRetriever requires langchain-core. "
                "Install with: pip install 'forget-rag[langchain]'"
            ) from e
        return ForgettingRetriever
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
