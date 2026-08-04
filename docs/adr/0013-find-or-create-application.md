# 0013: `find_or_create_application` tool

## Status

Accepted.

## Context

Per the README, as documented before this ADR: `push_to_tracker` "updates
an existing tracked row by Notion page ID — never creates a new row or
searches for one." That means, for any newly-found posting, the calling
assistant must already know which row (if any) to update, with no tool
support for the search-or-create decision itself. This is independently
verifiable from the README and the existing `push_to_tracker` docstring
alone — it does not depend on any specific retrospective incident.

## Decision

### A new tool, not a mode on `push_to_tracker`

`find_or_create_application(company, role, source_url=None, dry_run=False)`
is a separate MCP tool rather than a flag on `push_to_tracker`. The two
tools answer different questions — "is this a new posting or one I
already track" versus "record a fit analysis against a row I already
have" — and `push_to_tracker`'s contract (never creates, only updates) is
worth keeping simple and unchanged.

Returns `{"job_id": ..., "created": bool}`. Under `dry_run=True`, only
searches — never creates, even if no match is found (`job_id: None,
created: False` in that case).

### Matching: exact text, not fuzzy

`find_by_company_role` does a case-insensitive exact-text match against
the schema's `company`/`role` manual fields (`Company`/`Role` in the
example schema). This is a deliberate scope boundary: near-duplicate
postings (same company/title, different underlying req) are not
deduplicated by this tool — that's a separate, lower-priority concern
tracked in `docs/roadmap.md`.

### Requires `company` and `role` fields in `tracking_schema.yaml`

Both `NotionTrackingStore.find_by_company_role` and `.create_application`
require the schema to declare `company` and `role` fields with a
`notion.property` set (manual fields, same as `tracking_schema.example.yaml`
already has). Missing either raises a clear `RuntimeError` rather than a
confusing downstream failure — consistent with how the rest of this
project treats a schema that can't support what's being asked of it
(see ADR 0011's structural-vs-per-field validation split).

### Notion property types are read from the live database, not declared in the schema

To create a new page, the Notion API needs a value for the database's
title-type property (every Notion database has exactly one). Rather than
adding a new schema flag to mark which manual field is the title, the
implementation queries `databases.retrieve(...)["properties"]` at
call time and reads each property's actual `type` directly from Notion —
the authoritative source, always correct, and one less thing for the user
to configure by hand. `company` and `role` must resolve to a `title` or
`rich_text` property this way, or `create_application` raises a clear
error naming the unsupported type.

`source_url`, if given, is written to the schema's `jd_link` field (if
declared) when its live Notion type is `url` or `rich_text` — otherwise
it's silently omitted, matching the warn-and-skip spirit of the rest of
this codebase for a nice-to-have field, rather than failing the whole
create over one optional property.

`mapping.py`'s `_notion_property_payload`/`parse_notion_property` (now
public as `notion_property_payload`, since `notion_store.py` needs it
directly for the same reason `build_notion_properties_from_schema`
already did) gained `title` and `url` support alongside the existing
`select`/`rich_text`.

### `SQLiteTrackingStore` doesn't support this

`find_by_company_role`/`create_application` raise `NotImplementedError` on
`SQLiteTrackingStore` — that backend has no concept of manual fields
(company, role) at all, by design (see ADR 0011's "SQLite has no concept
of Notion's manual fields" note). Not currently reachable anyway, since
the server only wires up `NotionTrackingStore` today.

## Consequences

- The calling assistant now has a tool-supported answer to "have I
  already tracked this posting" instead of needing to reconstruct that
  from `list_applications` results itself.
- A newly-created row only has `company`, `role`, and optionally `jd_link`
  set — every other manual field (comp range, source, work arrangement,
  level, posting type, applied date, date posted) is left for the user to
  fill in by hand in Notion, the same "manual fields are the user's, not
  the tool's" boundary ADR 0011 established for `push_to_tracker`.
- `NotionTrackingStore`'s page-listing pagination logic (previously
  inlined in `list_analyses`) is now a shared `_iter_raw_pages` generator,
  reused by `find_by_company_role`.
- Near-duplicate detection (same company/role text, different underlying
  req) is explicitly out of scope for this tool — see `docs/roadmap.md`.
