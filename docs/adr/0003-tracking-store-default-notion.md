# 0003: Tracking store default — Notion

## Status

Accepted

## Context

The `TrackingStore` interface (ADR 0001) needs a default implementation.
The author already tracks job applications in Notion and wants fit-analysis
results written there directly, rather than maintaining a separate system
of record. Not everyone uses Notion, though, and requiring it would exclude
anyone who wants to run this project without an external account or API
key.

## Decision

Ship `NotionTrackingStore`
(`src/job_search_mcp/tracking_store/notion_store.py`) as the default
`TrackingStore` implementation, writing fit-analysis results to the
author's existing Notion tracking database.

A local SQLite implementation is the intended zero-dependency fallback for
anyone without Notion — no account, no API key, no network access
required. It is not built in this phase, but the `TrackingStore` interface
is designed so that it can be added as a sibling implementation
(`sqlite_store.py`) without any change to matching logic, per ADR 0001.

## Consequences

- The author's fit-analysis results land directly in the tracking system
  already used for job-search workflow, with no manual copy step.
- Notion's API and rate limits become an operational concern for that
  implementation specifically, not for the project as a whole.
- Anyone without Notion is blocked until a SQLite (or other) implementation
  exists; this is an acknowledged gap for this phase, not a permanent
  requirement to use Notion.
- The specific fields written to Notion are addressed separately in ADR
  0004, since the mapping between an analysis result and Notion database
  properties is its own decision with its own known limitations.
