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
    notion_property_payload,
    parse_notion_property,
)
from job_search_mcp.tracking_store.schema import TrackingField, TrackingSchema

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
        return [self._parse_page(page) for page in self._iter_raw_pages()]

    def find_by_company_role(self, company: str, role: str) -> str | None:
        company_field = self._field("company")
        role_field = self._field("role")
        if not company_field or not company_field.notion_property or not role_field or not role_field.notion_property:
            raise RuntimeError(
                "find_or_create_application requires 'company' and 'role' fields with a "
                "notion.property declared in your tracking_schema.yaml."
            )
        known_properties = self._client.databases.retrieve(database_id=self.database_id).get("properties", {})
        company_type = known_properties.get(company_field.notion_property, {}).get("type")
        role_type = known_properties.get(role_field.notion_property, {}).get("type")

        target_company = company.strip().casefold()
        target_role = role.strip().casefold()
        for page in self._iter_raw_pages():
            if page.get("archived"):
                continue
            properties = page["properties"]
            page_company = parse_notion_property(properties.get(company_field.notion_property, {}), company_type)
            page_role = parse_notion_property(properties.get(role_field.notion_property, {}), role_type)
            if (
                page_company is not None
                and page_role is not None
                and page_company.strip().casefold() == target_company
                and page_role.strip().casefold() == target_role
            ):
                return page["id"]
        return None

    def create_application(self, company: str, role: str, source_url: str | None = None) -> str:
        company_field = self._field("company")
        role_field = self._field("role")
        if not company_field or not company_field.notion_property or not role_field or not role_field.notion_property:
            raise RuntimeError(
                "find_or_create_application requires 'company' and 'role' fields with a "
                "notion.property declared in your tracking_schema.yaml."
            )
        known_properties = self._client.databases.retrieve(database_id=self.database_id).get("properties", {})

        properties: dict = {}
        for field, value in ((company_field, company), (role_field, role)):
            notion_type = known_properties.get(field.notion_property, {}).get("type")
            if notion_type not in ("title", "rich_text"):
                raise RuntimeError(
                    f"Notion property {field.notion_property!r} (field {field.key!r}) has "
                    f"unsupported type {notion_type!r} for find_or_create_application — must be "
                    "'title' or 'rich_text'."
                )
            properties[field.notion_property] = notion_property_payload(notion_type, value)

        if source_url:
            jd_link_field = self._field("jd_link")
            if jd_link_field and jd_link_field.notion_property:
                link_type = known_properties.get(jd_link_field.notion_property, {}).get("type")
                if link_type in ("url", "rich_text"):
                    properties[jd_link_field.notion_property] = notion_property_payload(link_type, source_url)

        page = self._client.pages.create(parent={"database_id": self.database_id}, properties=properties)
        return page["id"]

    def update_status(self, job_id: str, status: str) -> None:
        status_field = self._field("status")
        if not status_field or not status_field.notion_property:
            raise RuntimeError(
                "update_status requires a 'status' field with a notion.property declared in "
                "your tracking_schema.yaml."
            )
        payload = notion_property_payload(status_field.notion_type or "select", status)
        try:
            self._client.pages.update(page_id=job_id, properties={status_field.notion_property: payload})
        except APIResponseError as exc:
            if exc.code == APIErrorCode.ObjectNotFound:
                raise RuntimeError(f"No Notion page found for job_id={job_id!r}.") from exc
            raise

    def _field(self, key: str) -> TrackingField | None:
        return next((field for field in self.schema.fields if field.key == key), None)

    def _iter_raw_pages(self):
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

        cursor = None
        while True:
            response = self._client.data_sources.query(
                data_source_id=data_source_id, start_cursor=cursor
            )
            yield from response["results"]
            if not response.get("has_more"):
                break
            cursor = response["next_cursor"]

    def _parse_page(self, page: dict) -> dict:
        properties = page["properties"]
        result: dict = {"job_id": page["id"]}
        for field in self.schema.tool_populated_fields():
            result[field.key] = parse_notion_property(
                properties.get(field.notion_property, {}), field.notion_type
            )
        return result
