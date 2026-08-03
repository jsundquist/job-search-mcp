"""SQLite implementation of TrackingStore.

Zero-dependency fallback for anyone without Notion — no account, no API
key, no network access required (see
docs/adr/0003-tracking-store-default-notion.md). Schema covers only the
fields push_to_tracker maps (status, fit_rating, notes) — see mapping.py.
"""

from __future__ import annotations

import sqlite3

from job_search_mcp.fit_verdict import FitVerdict
from job_search_mcp.tracking_store.mapping import build_tracking_fields

_SCHEMA = """
CREATE TABLE IF NOT EXISTS analyses (
    job_id TEXT PRIMARY KEY,
    status TEXT NOT NULL,
    fit_rating TEXT NOT NULL,
    notes TEXT NOT NULL
)
"""


class SQLiteTrackingStore:
    """TrackingStore backed by a local SQLite database."""

    def __init__(self, db_path: str) -> None:
        self.db_path = db_path
        self._connection = sqlite3.connect(db_path)
        self._connection.execute(_SCHEMA)
        self._connection.commit()

    def record_analysis(self, job_id: str, analysis: FitVerdict) -> None:
        fields = build_tracking_fields(analysis)
        self._connection.execute(
            """
            INSERT INTO analyses (job_id, status, fit_rating, notes)
            VALUES (:job_id, :status, :fit_rating, :notes)
            ON CONFLICT(job_id) DO UPDATE SET
                status = excluded.status,
                fit_rating = excluded.fit_rating,
                notes = excluded.notes
            """,
            {"job_id": job_id, **fields},
        )
        self._connection.commit()

    def get_analysis(self, job_id: str) -> dict | None:
        row = self._connection.execute(
            "SELECT job_id, status, fit_rating, notes FROM analyses WHERE job_id = ?",
            (job_id,),
        ).fetchone()
        if row is None:
            return None
        return self._row_to_dict(row)

    def list_analyses(self) -> list[dict]:
        rows = self._connection.execute(
            "SELECT job_id, status, fit_rating, notes FROM analyses"
        ).fetchall()
        return [self._row_to_dict(row) for row in rows]

    def close(self) -> None:
        self._connection.close()

    @staticmethod
    def _row_to_dict(row: tuple) -> dict:
        job_id, status, fit_rating, notes = row
        return {"job_id": job_id, "status": status, "fit_rating": fit_rating, "notes": notes}
