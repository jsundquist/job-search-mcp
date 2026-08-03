"""SQLite implementation of TrackingStore.

Zero-dependency fallback for anyone without Notion — no account, no API
key, no network access required (see
docs/adr/0003-tracking-store-default-notion.md). Reads the user's
TrackingSchema (schema.py, docs/adr/0011) for which tool-populated fields
to track; only fields with a `sqlite.column` are tracked here at all —
SQLite has no concept of the manual, pre-existing-row fields Notion
tracks (company, comp range, source, ...).
"""

from __future__ import annotations

import logging
import sqlite3

from job_search_mcp.fit_verdict import FitVerdict
from job_search_mcp.tracking_store.mapping import (
    build_sqlite_fields_from_schema,
    sqlite_tool_populated_fields,
)
from job_search_mcp.tracking_store.schema import TrackingSchema

logger = logging.getLogger(__name__)


class SQLiteTrackingStore:
    """TrackingStore backed by a local SQLite database."""

    def __init__(self, db_path: str, schema: TrackingSchema) -> None:
        self.db_path = db_path
        self.schema = schema
        self._fields = sqlite_tool_populated_fields(schema)
        self._connection = sqlite3.connect(db_path)
        self._ensure_table()

    def _ensure_table(self) -> None:
        # Column names come from TrackingField.sqlite_column, which
        # schema.py already restricts to a safe identifier shape at load
        # time — see schema.py's _SQLITE_IDENTIFIER_RE.
        # Not NOT NULL: a warn-and-skip field (see build_sqlite_fields_from_schema)
        # can leave a column unset on a given write without breaking the insert.
        column_defs = ", ".join(f"{field.sqlite_column} TEXT" for field in self._fields)
        columns_clause = f"job_id TEXT PRIMARY KEY, {column_defs}" if self._fields else "job_id TEXT PRIMARY KEY"
        self._connection.execute(f"CREATE TABLE IF NOT EXISTS analyses ({columns_clause})")
        self._connection.commit()

    def _select_columns(self) -> str:
        column_names = ", ".join(f.sqlite_column for f in self._fields)
        return f"job_id, {column_names}" if self._fields else "job_id"

    def record_analysis(self, job_id: str, analysis: FitVerdict) -> list[str]:
        values, warnings = build_sqlite_fields_from_schema(self.schema, analysis)
        for warning in warnings:
            logger.warning(warning)

        if not values:
            self._connection.execute("INSERT INTO analyses (job_id) VALUES (:job_id) ON CONFLICT DO NOTHING", {"job_id": job_id})
        else:
            columns = ", ".join(values.keys())
            placeholders = ", ".join(f":{column}" for column in values)
            updates = ", ".join(f"{column} = excluded.{column}" for column in values)
            self._connection.execute(
                f"""
                INSERT INTO analyses (job_id, {columns})
                VALUES (:job_id, {placeholders})
                ON CONFLICT(job_id) DO UPDATE SET {updates}
                """,
                {"job_id": job_id, **values},
            )
        self._connection.commit()
        return warnings

    def get_analysis(self, job_id: str) -> dict | None:
        row = self._connection.execute(
            f"SELECT {self._select_columns()} FROM analyses WHERE job_id = ?",
            (job_id,),
        ).fetchone()
        if row is None:
            return None
        return self._row_to_dict(row)

    def list_analyses(self) -> list[dict]:
        rows = self._connection.execute(f"SELECT {self._select_columns()} FROM analyses").fetchall()
        return [self._row_to_dict(row) for row in rows]

    def close(self) -> None:
        self._connection.close()

    def _row_to_dict(self, row: tuple) -> dict:
        job_id, *values = row
        result = {"job_id": job_id}
        for field, value in zip(self._fields, values, strict=True):
            result[field.key] = value
        return result
