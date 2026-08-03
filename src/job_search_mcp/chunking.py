"""Light section-based chunking for resume text.

Not a general document chunker — a small structural heuristic tuned to the
shape typical of a resume: short section headers, longer role/title/date
lines, and bulleted achievement details. Chunk boundaries:

  - a short, digit-free line (e.g. "Experience", "Technical Skills") is
    treated as a section header and always starts a new chunk
  - a longer non-bullet line (a role/title/company/date line) starts a new
    chunk only if the current chunk has already accumulated bulleted
    content — this is what separates one role/project from the next
  - bulleted lines never start a new chunk; they accumulate under whatever
    role/section heading precedes them

This is intentionally simple, not NLP-based section detection. Text
extracted from PDF/DOCX may preserve line breaks less faithfully than
plain text/markdown, so chunk boundaries can be less precise for those
formats — an accepted tradeoff for this phase. A lone short trailing line
(e.g. a single-word line right after a section header, with no comma or
digit) can also be misread as its own header and split off; also accepted
for this phase rather than adding more heuristics.
"""

from __future__ import annotations

_BULLET_PREFIXES = ("*", "-", "•")
_MAX_HEADER_TOKENS = 4


def _is_bullet(line: str) -> bool:
    return line.startswith(_BULLET_PREFIXES)


def _is_section_header(line: str) -> bool:
    tokens = line.split()
    if not tokens or len(tokens) > _MAX_HEADER_TOKENS:
        return False
    if "," in line:
        return False
    return not any(char.isdigit() for char in line)


def chunk_resume_text(text: str) -> list[str]:
    """Split resume text into light, section/role-sized chunks."""
    chunks: list[str] = []
    buffer: list[str] = []
    buffer_has_bullets = False

    def flush() -> None:
        nonlocal buffer, buffer_has_bullets
        if buffer:
            chunks.append("\n".join(buffer).strip())
        buffer = []
        buffer_has_bullets = False

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if _is_bullet(line):
            buffer.append(line)
            buffer_has_bullets = True
        elif _is_section_header(line):
            flush()
            buffer.append(line)
        else:
            if buffer_has_bullets:
                flush()
            buffer.append(line)
    flush()

    return chunks
