"""Notion implementation of TrackingStore.

Default tracking store adapter. v1 maps analysis results onto a small,
hardcoded set of Notion database properties — see
docs/adr/0004-tracking-field-mapping-v1-shortcut.md.

Not yet implemented — scaffolding only.
"""

from __future__ import annotations


class NotionTrackingStore:
    """TrackingStore backed by a Notion database."""

    def __init__(self, database_id: str, api_key: str) -> None:
        self.database_id = database_id
        self.api_key = api_key

    def record_analysis(self, job_id: str, analysis: dict) -> None:
        raise NotImplementedError

    def get_analysis(self, job_id: str) -> dict | None:
        raise NotImplementedError

    def list_analyses(self) -> list[dict]:
        raise NotImplementedError
