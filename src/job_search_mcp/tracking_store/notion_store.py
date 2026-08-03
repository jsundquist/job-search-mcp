"""Notion implementation of TrackingStore.

Default tracking store adapter. v1 maps analysis results onto a small,
hardcoded set of Notion database properties — see
docs/adr/0004-tracking-field-mapping-v1-shortcut.md and mapping.py.

`job_id` is the Notion page ID of a row the author already tracks (added
when the job was first found) — record_analysis updates that existing
row's Status/Fit Rating/Key Notes in place. It does not create new rows
or search for a matching row; the caller supplies the page ID directly.
"""

from __future__ import annotations

from notion_client import Client
from notion_client.errors import APIErrorCode, APIResponseError

from job_search_mcp.fit_verdict import FitVerdict
from job_search_mcp.tracking_store.mapping import (
    FIT_RATING_PROPERTY,
    KEY_NOTES_PROPERTY,
    STATUS_PROPERTY,
    build_notion_properties,
)


class NotionTrackingStore:
    """TrackingStore backed by the author's existing Notion tracking database."""

    def __init__(self, database_id: str, api_key: str) -> None:
        self.database_id = database_id
        self.api_key = api_key
        self._client = Client(auth=api_key)

    def record_analysis(self, job_id: str, analysis: FitVerdict) -> None:
        try:
            self._client.pages.update(page_id=job_id, properties=build_notion_properties(analysis))
        except APIResponseError as exc:
            if exc.code == APIErrorCode.ObjectNotFound:
                raise RuntimeError(
                    f"No Notion page found for job_id={job_id!r}. push_to_tracker only updates "
                    "an existing tracked row — add the job to Notion first, then retry with its "
                    "page ID."
                ) from exc
            raise

    def get_analysis(self, job_id: str) -> dict | None:
        page = self._client.pages.retrieve(page_id=job_id)
        if page.get("archived"):
            return None
        return self._parse_page(page)

    def list_analyses(self) -> list[dict]:
        # Notion's 2025-09 API splits a database into one or more data
        # sources; querying rows goes through data_sources.query, not
        # databases.query. The author's tracker has a single data source.
        database = self._client.databases.retrieve(database_id=self.database_id)
        data_sources = database["data_sources"]
        if not data_sources:
            raise RuntimeError(
                f"Notion database {self.database_id!r} has no data sources — check "
                "NOTION_DATABASE_ID."
            )
        data_source_id = data_sources[0]["id"]

        results = []
        cursor = None
        while True:
            response = self._client.data_sources.query(
                data_source_id=data_source_id, start_cursor=cursor
            )
            results.extend(self._parse_page(page) for page in response["results"])
            if not response.get("has_more"):
                break
            cursor = response["next_cursor"]
        return results

    def _parse_page(self, page: dict) -> dict:
        properties = page["properties"]
        status = properties.get(STATUS_PROPERTY, {}).get("select") or {}
        fit_rating = properties.get(FIT_RATING_PROPERTY, {}).get("select") or {}
        notes_parts = properties.get(KEY_NOTES_PROPERTY, {}).get("rich_text") or []
        return {
            "job_id": page["id"],
            "status": status.get("name"),
            "fit_rating": fit_rating.get("name"),
            "notes": "".join(part.get("plain_text", "") for part in notes_parts),
        }
