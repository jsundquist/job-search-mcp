"""TrackingStore adapter interface.

See docs/adr/0001-adapter-pattern-for-storage-and-input.md and
docs/adr/0003-tracking-store-default-notion.md.
"""

from __future__ import annotations

from typing import Protocol


class TrackingStore(Protocol):
    """Persistence for job fit-analysis records.

    Implementations own the mapping from an analysis result to whatever
    fields their backing store exposes (see
    docs/adr/0004-tracking-field-mapping-v1-shortcut.md for the current,
    hardcoded v1 field mapping).
    """

    def record_analysis(self, job_id: str, analysis: dict) -> None:
        """Write a fit-analysis result for the given job."""
        ...

    def get_analysis(self, job_id: str) -> dict | None:
        """Return the stored analysis for a job, if any."""
        ...

    def list_analyses(self) -> list[dict]:
        """Return all stored analyses."""
        ...
