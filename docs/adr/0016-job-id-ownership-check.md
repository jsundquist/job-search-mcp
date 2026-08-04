# 0016: Verify `job_id` ownership before writing in `NotionTrackingStore`

## Status

Accepted.

## Context

`push_to_tracker` and `update_status` both take a bare `job_id` (a Notion
page ID) and pass it straight to `notion_client`'s `pages.update` in
`NotionTrackingStore.record_analysis`/`update_status`
(`src/job_search_mcp/tracking_store/notion_store.py`). Neither method
checked that the page actually belongs to `self.database_id` — the
Notion API will happily update *any* page the integration token can
reach, not just rows in the configured tracking database.

This was a pre-existing property of `record_analysis` (`job_id` "is the
Notion page ID of a row the author already tracks... the caller supplies
the page ID directly," per this file's original module docstring), and
`update_status` (added in `docs/adr/0014-update-status-tool.md`) inherited
it unchanged.

It matters because of the threat model
`docs/adr/0015-prompt-injection-defense-for-job-description-text.md`
already establishes: `job_id` values reaching these tools can originate
from an LLM agent whose reasoning was shaped by untrusted, scraped
job-posting text. A posting containing an embedded instruction (and a
plausible-looking page-ID string) could induce the calling agent to
invoke `update_status` or `push_to_tracker` against a page outside the
tracked database — some other page the same integration happens to have
access to — silently corrupting or overwriting it. This is a concrete
extension of a threat model this project has already accepted for
`job_description`, not a new hypothetical multi-tenant concern (per ADR
0015, this remains a personal single-user tool).

## Decision

`NotionTrackingStore` gets a private `_assert_owned(job_id)` check, called
before every `pages.update` in `record_analysis` and `update_status`. It
does a `pages.retrieve(page_id=job_id)` and confirms the returned page's
`parent` resolves to `self.database_id` — either directly
(`parent.type == "database_id"`) or via one of the database's known data
sources (`parent.type == "data_source_id"`, the shape Notion's 2025-09 API
uses for rows created against a database's data source; see the existing
`_iter_raw_pages` comment on this API split). IDs are compared in a
dashed/undashed-normalized form, since Notion accepts both. A page that
resolves to neither raises a `RuntimeError` and the write never happens.

This costs one extra `pages.retrieve` call per write — acceptable at this
tool's personal scale — and requires no changes to the `TrackingStore`
protocol (`base.py`) or any MCP tool signature in `server.py`.

`SQLiteTrackingStore` has no equivalent gap: it operates on a single local
`analyses` table keyed by `job_id`, with no concept of a page belonging to
a different "database" to escape into. No change needed there.

### `update_status` also validates `status` against configured options

While in this code path: `update_status` previously wrote the caller's
`status` string straight into the Notion `select` payload with no local
check against the field's actual configured options. It now fetches the
database's known properties (the same `databases.retrieve` pattern
`record_analysis` already uses) and rejects an unrecognized value before
attempting the write, naming the valid options in the error. This is a
correctness/UX fix, not a security boundary — the write was already
confined to the one field on the one (now ownership-checked) row — but it
turns an opaque Notion API failure into a clear local error.

## Consequences

- `push_to_tracker` and `update_status` now refuse to write to a page
  outside the configured tracking database, closing the gap described
  above.
- One additional Notion API call (`pages.retrieve`) per write.
- `update_status` rejects unrecognized status strings locally instead of
  relying on the Notion API to reject (or, for some property types,
  silently accept) them.
