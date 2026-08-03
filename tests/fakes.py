"""Deterministic Embedder test double.

Not backed by any real model — turns text into a small fixed-size vector
via hashing, so unit tests run fast and fully offline while still
exercising real cosine-similarity ranking through InMemoryVectorStore.
"""

from __future__ import annotations

import hashlib

_DIM = 16


class FakeEmbedder:
    """Deterministic Embedder: same text always maps to the same vector."""

    def embed(self, text: str) -> list[float]:
        digest = hashlib.sha256(text.encode("utf-8")).digest()
        return [b / 255.0 for b in digest[:_DIM]]

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        return [self.embed(text) for text in texts]
