"""Notion implementation of TrackingStore.

Reads the user's TrackingSchema (schema.py, docs/adr/0011) to know which
Notion properties to write/read — no hardcoded field list (see
docs/adr/0004-tracking-field-mapping-v1-shortcut.md, superseded by
docs/adr/0011-configurable-tracking-field-schema.md).

`job_id` is the Notion page ID of a row the author already tracks (added
when the job was first found) — record_analysis updates that existing
row's tool-populated fields in place. It does not create new rows or
search for a matching row; the caller supplies the page ID directly.
"""

from __future__ import annotations

import logging

from notion_client import Client
from notion_client.errors import APIErrorCode, APIResponseError

from job_search_mcp.fit_verdict import FitVerdict
from job_search_mcp.tracking_store.mapping import (
    build_notion_properties_from_schema,
    parse_notion_property,
)
from job_search_mcp.tracking_store.schema import TrackingSchema

logger = logging.getLogger(__name__)


class NotionTrackingStore:
    """TrackingStore backed by the author's existing Notion tracking database."""

    def __init__(self, database_id: str, api_key: str, schema: TrackingSchema) -> None:
        self.database_id = database_id
        self.api_key = api_key
        self.schema = schema
        self._client = Client(auth=api_key)

    def record_analysis(self, job_id: str, analysis: FitVerdict) -> list[str]:
        known_properties = self._client.databases.retrieve(database_id=self.database_id).get("properties", {})
        properties, warnings = build_notion_properties_from_schema(self.schema, analysis, known_properties)
        for warning in warnings:
            logger.warning(warning)

        try:
            self._client.pages.update(page_id=job_id, properties=properties)
        except APIResponseError as exc:
            if exc.code == APIErrorCode.ObjectNotFound:
                raise RuntimeError(
                    f"No Notion page found for job_id={job_id!r}. push_to_tracker only updates "
                    "an existing tracked row — add the job to Notion first, then retry with its "
                    "page ID."
                ) from exc
            raise
        return warnings

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
        result: dict = {"job_id": page["id"]}
        for field in self.schema.tool_populated_fields():
            result[field.key] = parse_notion_property(
                properties.get(field.notion_property, {}), field.notion_type
            )
        return result
