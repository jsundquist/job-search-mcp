"""Local Embedder implementation using sentence-transformers.

Default embeddings adapter (ADR 0006): runs fully offline on local
hardware, no API key or per-call cost. Model defaults to
all-MiniLM-L6-v2 — small, fast, and a common baseline choice for
retrieval over short documents like a resume.
"""

from __future__ import annotations

from sentence_transformers import SentenceTransformer

DEFAULT_MODEL_NAME = "all-MiniLM-L6-v2"


class SentenceTransformersEmbedder:
    """Embedder backed by a local sentence-transformers model."""

    def __init__(self, model_name: str = DEFAULT_MODEL_NAME) -> None:
        self.model_name = model_name
        self._model = SentenceTransformer(model_name)

    def embed(self, text: str) -> list[float]:
        return self._model.encode(text, convert_to_numpy=True).tolist()

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        return self._model.encode(texts, convert_to_numpy=True).tolist()
