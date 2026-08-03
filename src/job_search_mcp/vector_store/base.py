"""VectorStore adapter interface.

See docs/adr/0001-adapter-pattern-for-storage-and-input.md and
docs/adr/0002-vector-store-default-qdrant.md.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol


@dataclass
class VectorRecord:
    """A single embedded chunk of resume/experience content plus its metadata."""

    id: str
    vector: list[float]
    payload: dict = field(default_factory=dict)


class VectorStore(Protocol):
    """Storage and retrieval of embedded resume/experience chunks.

    Implementations are responsible only for persistence and similarity
    search — embedding generation and matching logic live elsewhere.
    """

    def upsert(self, records: list[VectorRecord]) -> None:
        """Insert or update the given records."""
        ...

    def search(self, query_vector: list[float], top_k: int = 5) -> list[VectorRecord]:
        """Return the top_k records most similar to query_vector."""
        ...

    def delete(self, ids: list[str]) -> None:
        """Remove records by id."""
        ...
