# 0005: Resume source default — file-based (text/markdown, PDF, DOCX)

## Status

Accepted

## Context

The `ResumeSource` interface (ADR 0001) needs a default implementation. The
author's resume lives in Google Drive, and today is retrieved by manually
exporting it as PDF or DOCX before it can be used by anything else. A
first `ResumeSource` implementation needs to cover that actual workflow —
not an idealized one — while leaving room for a more direct integration
later without redesigning the interface.

## Decision

Ship `FileResumeSource` (`src/job_search_mcp/resume_source/file_source.py`)
as the default `ResumeSource` implementation, parsing plain text/markdown,
PDF, and DOCX files from a local path. Plain text/markdown is included
because it is the simplest possible case and useful for testing; PDF and
DOCX are included because they are the author's actual current export
formats.

A Google Drive-backed `ResumeSource` — reading the resume directly from
Drive via its API instead of requiring a manual export step — is noted
here as a natural future implementation, not designed or built in this
phase. Because `ResumeSource` only requires producing plain text content
(see `base.py`), that future implementation is a new sibling file, not a
redesign: it fetches content from a different place and still returns text
the same way `FileResumeSource` does.

## Consequences

- Covers the author's real current workflow immediately (manual PDF/DOCX
  export), without requiring Google Drive API access to get started.
- Anyone else can use a plain text or markdown resume with zero setup.
- The manual export step remains a point of friction until the Google
  Drive-backed implementation exists; that is accepted for this phase.
- PDF/DOCX parsing introduces a dependency on parsing libraries and their
  respective failure modes (malformed files, unusual formatting) that a
  plain-text source doesn't have — acceptable tradeoff for covering the
  author's real files.
