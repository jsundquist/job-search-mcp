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

    def find_by_company_role(self, company: str, role: str) -> str | None:
        """Return the job_id of an existing tracked row matching company+role, if any.

        Exact, case-insensitive match against the schema's 'company'/'role'
        manual fields. Not every backend can support this (e.g. SQLite has
        no concept of manual fields) — such backends raise NotImplementedError.
        """
        ...

    def create_application(self, company: str, role: str, source_url: str | None = None) -> str:
        """Create a new tracked row for a company+role and return its job_id.

        Only sets the fields needed to identify the row (company, role, and
        — if the schema declares a compatible field — source_url); every
        other manual field is left for the user to fill in by hand, same
        boundary ADR 0011 established for push_to_tracker.
        """
        ...

    def update_status(self, job_id: str, status: str) -> None:
        """Set the status field on an existing tracked row directly.

        Distinct from record_analysis: this is for candidate-reported
        lifecycle events (Applied, Rejected, ...), not a FitVerdict.
        """
        ...
