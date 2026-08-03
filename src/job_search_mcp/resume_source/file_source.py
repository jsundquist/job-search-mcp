"""File-based implementation of ResumeSource.

Default resume source adapter: parses plain text/markdown, PDF, and DOCX
files. A Google Drive-backed ResumeSource is a natural future
implementation of the same interface — see
docs/adr/0005-resume-source-default-file-based.md.

Not yet implemented — scaffolding only.
"""

from __future__ import annotations

from pathlib import Path


class FileResumeSource:
    """ResumeSource backed by a local file (.txt, .md, .pdf, or .docx)."""

    def __init__(self, path: Path) -> None:
        self.path = path

    def get_content(self) -> str:
        raise NotImplementedError
