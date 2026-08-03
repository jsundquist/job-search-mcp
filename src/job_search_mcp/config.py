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


@dataclass
class NotionConfig:
    database_id: str
    api_key: str

    @classmethod
    def from_env(cls) -> NotionConfig:
        database_id = os.environ.get("NOTION_DATABASE_ID")
        api_key = os.environ.get("NOTION_API_KEY")
        if not database_id or not api_key:
            raise RuntimeError(
                "NOTION_DATABASE_ID and NOTION_API_KEY must be set (see .env.example)."
            )
        return cls(database_id=database_id, api_key=api_key)
