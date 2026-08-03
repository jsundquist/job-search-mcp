"""Embedder adapter interface.

See docs/adr/0001-adapter-pattern-for-storage-and-input.md and
docs/adr/0006-embeddings-choice-open.md.
"""

from __future__ import annotations

from typing import Protocol


class Embedder(Protocol):
    """Turns text into a vector for storage in / query against a VectorStore."""

    def embed(self, text: str) -> list[float]:
        """Return the embedding vector for a single piece of text."""
        ...

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Return embedding vectors for multiple texts, in order."""
        ...
