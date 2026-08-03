"""TrackingStore adapter interface.

See docs/adr/0001-adapter-pattern-for-storage-and-input.md and
docs/adr/0003-tracking-store-default-notion.md.
"""

from __future__ import annotations

from typing import Protocol

from job_search_mcp.fit_verdict import FitVerdict


class TrackingStore(Protocol):
    """Persistence for job fit-analysis records.

    Implementations read a user-declared TrackingSchema (schema.py, ADR
    0011) for which fields to write/read — not a fixed field list.
    """

    def record_analysis(self, job_id: str, analysis: FitVerdict) -> list[str]:
        """Write a fit-analysis result for the given job.

        Returns any warnings for tool-populated fields that were skipped
        because the schema misconfigured them (see mapping.py's
        build_notion_properties_from_schema/build_sqlite_fields_from_schema) —
        an empty list means every declared field was written cleanly.
        """
        ...

    def get_analysis(self, job_id: str) -> dict | None:
        """Return the stored analysis for a job, if any."""
        ...

    def list_analyses(self) -> list[dict]:
        """Return all stored analyses."""
        ...
