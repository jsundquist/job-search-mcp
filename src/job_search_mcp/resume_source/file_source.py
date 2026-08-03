"""File-based implementation of ResumeSource.

Default resume source adapter: parses plain text/markdown, PDF, and DOCX
files. A Google Drive-backed ResumeSource is a natural future
implementation of the same interface — see
docs/adr/0005-resume-source-default-file-based.md.

PDF extraction uses pypdf; DOCX extraction uses python-docx. Both are
well-established, actively maintained libraries rather than custom parsing.

PDF extraction uses pypdf's "layout" mode rather than its default plain
mode — for at least one real-world PDF, default mode fragmented the text
into near one-word-per-line output (each visually-spaced word became its
own line), which broke line-based resume chunking downstream. Layout mode
preserves the PDF's visual line wrapping much more faithfully.

DOCX bulleted list items store their bullet as paragraph-level numbering
metadata (a <w:numPr> element), not as a literal character in the
paragraph's text — python-docx's paragraph.text drops it entirely. Since
downstream chunking (chunking.py) detects bullets by a literal leading
character, a "•" is prepended to paragraphs that carry list-numbering
metadata so bullet structure survives extraction as plain text.
"""

from __future__ import annotations

from pathlib import Path

import docx
from pypdf import PdfReader

TEXT_SUFFIXES = {".txt", ".md"}
PDF_SUFFIXES = {".pdf"}
DOCX_SUFFIXES = {".docx"}

_WORD_NUMPR_XPATH = ".//{http://schemas.openxmlformats.org/wordprocessingml/2006/main}numPr"


class FileResumeSource:
    """ResumeSource backed by a local file (.txt, .md, .pdf, or .docx)."""

    def __init__(self, path: Path | str) -> None:
        self.path = Path(path)

    def get_content(self) -> str:
        suffix = self.path.suffix.lower()
        if suffix in TEXT_SUFFIXES:
            return self._read_text()
        if suffix in PDF_SUFFIXES:
            return self._read_pdf()
        if suffix in DOCX_SUFFIXES:
            return self._read_docx()
        raise ValueError(
            f"Unsupported resume file type: {suffix!r} ({self.path}). "
            f"Supported: {sorted(TEXT_SUFFIXES | PDF_SUFFIXES | DOCX_SUFFIXES)}"
        )

    def _read_text(self) -> str:
        return self.path.read_text(encoding="utf-8-sig")

    def _read_pdf(self) -> str:
        reader = PdfReader(str(self.path))
        return "\n".join(page.extract_text(extraction_mode="layout") or "" for page in reader.pages)

    def _read_docx(self) -> str:
        document = docx.Document(str(self.path))
        lines = []
        for paragraph in document.paragraphs:
            is_list_item = paragraph._p.find(_WORD_NUMPR_XPATH) is not None
            prefix = "• " if is_list_item else ""
            lines.append(f"{prefix}{paragraph.text}")
        return "\n".join(lines)
