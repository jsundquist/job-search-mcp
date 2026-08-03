"""Env-var based configuration, loaded from .env if present."""

from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


@dataclass
class QdrantConfig:
    url: str
    api_key: str | None
    collection_name: str

    @classmethod
    def from_env(cls) -> QdrantConfig:
        url = os.environ.get("QDRANT_URL")
        collection_name = os.environ.get("QDRANT_COLLECTION_NAME")
        if not url or not collection_name:
            raise RuntimeError(
                "QDRANT_URL and QDRANT_COLLECTION_NAME must be set (see .env.example)."
            )
        return cls(
            url=url,
            api_key=os.environ.get("QDRANT_API_KEY") or None,
            collection_name=collection_name,
        )
