"""ResumeSource adapter interface.

See docs/adr/0001-adapter-pattern-for-storage-and-input.md and
docs/adr/0005-resume-source-default-file-based.md.
"""

from __future__ import annotations

from typing import Protocol


class ResumeSource(Protocol):
    """Retrieval of resume/experience content to be chunked and embedded.

    Implementations are responsible only for producing raw text content —
    chunking and embedding happen downstream.
    """

    def get_content(self) -> str:
        """Return the resume/experience content as plain text."""
        ...
