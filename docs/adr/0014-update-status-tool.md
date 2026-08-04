# 0014: `update_status` tool, decoupled from `FitVerdict`

## Status

Accepted.

## Context

Per `docs/adr/0011-configurable-tracking-field-schema.md` ("`status_fixed`
carries forward Phase 3's assumption, unchanged"): `status` can only be
written via `derived_from: status_fixed` on a `FitVerdict` passed to
`push_to_tracker`, which always sets the same constant (`STATUS_VALUE`,
`"Not yet applied"`). There is no documented way to update status alone
from an external event (a rejection email, a recruiter screen, an offer)
without constructing a full, partly-fabricated `FitVerdict` just to touch
one field. This is verifiable directly from ADR 0011 and `mapping.py`
alone — it doesn't depend on any specific retrospective incident.

This is a single-responsibility violation relative to the discipline this
project holds everywhere else: the `VectorStore`/`TrackingStore`/
`ResumeSource` adapter boundaries (ADR 0001), and `derived_from`'s
deliberately closed, tightly-scoped vocabulary (ADR 0011). A
candidate-reported status change is a fundamentally different kind of
event from a fit-analysis result, even though today both would write to
the same Notion field.

## Decision

### A new tool, not a new `derived_from` value

`update_status(job_id, status, dry_run=False)` is added as its own MCP
tool, explicitly documented as handling candidate-reported outcome events
("Applied", "Rejected", "Interviewing", "Offer", ...) rather than
fit-analysis results. It takes a plain `status: str`, not a `FitVerdict`
— there is no value here that could sensibly be *derived* from a fit
analysis; the whole point is that this event doesn't come from one.

`NotionTrackingStore.update_status` looks up the schema field with
`key == "status"`, requires it to have a `notion.property` declared (same
requirement style as ADR 0013's `find_by_company_role`/`create_application`),
and writes only that one property via `pages.update`, using the field's
declared `notion.type` (currently always `select` in practice, but not
hardcoded — falls back to `select` only if `notion.type` is unset).
`SQLiteTrackingStore.update_status` is implemented for real (unlike ADR
0013's `find_by_company_role`/`create_application`), since `status` is
already one of the three fields SQLite tracks — it upserts a row with
just the status column set if the job isn't already recorded.

### Dual-writer decision: last write wins, no locking

Once `update_status` exists alongside `push_to_tracker`'s
`derived_from: status_fixed`, there are two separate code paths that can
both mutate the tracker's `status` field. Per the same multi-writer
discipline ADR 0011 already applied to the Notion-vs-SQLite backend
question, this needs to be a deliberate, documented decision, not an
implicit gap:

**Decision: last write wins. No locking, no version check, no
reconciliation between the two paths.** This is judged acceptable because
`push_to_tracker`'s status write always happens exactly once, at initial
analysis time, setting a single fixed value (`"Not yet applied"`) — it is
never called again for the same row afterward in the tool's intended
usage. `update_status` calls, by contrast, happen zero or more times
after that, as real-world events occur. In practice the two paths don't
race: `push_to_tracker`'s write is expected to always precede any
`update_status` call for a given row, not interleave with it. If a caller
does call `push_to_tracker` again against a row that's already had its
status manually advanced (e.g. re-running analysis on an old posting),
its status write silently reverts the row to `"Not yet applied"` — this
is the same fixed-value overwrite behavior ADR 0011 already documented
for `push_to_tracker`'s status field, not a new risk introduced by this
ADR, and is called out here explicitly rather than left as a surprise.

## Consequences

- Recording a rejection, an applied date, or an interview no longer
  requires fabricating a `FitVerdict` — a genuine improvement to the
  single-responsibility boundary between fit analysis and lifecycle
  tracking.
- `TrackingStore.update_status` is now part of the adapter protocol;
  `SQLiteTrackingStore` implements it for real, `NotionTrackingStore` too.
- The dual-writer overwrite behavior above is a known, accepted trade-off,
  not a bug to fix later — re-running `push_to_tracker` against an
  already-advanced row will reset its status, exactly as it always could
  before this ADR (this ADR does not change `push_to_tracker`'s
  behavior at all, only adds a second, independent write path).
