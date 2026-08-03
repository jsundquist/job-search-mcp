# 0011: Configurable tracking field schema

## Status

Accepted. Supersedes the concrete v1 field mapping in
`docs/adr/0004-tracking-field-mapping-v1-shortcut.md` (that ADR's
"why a hardcoded mapping was the fastest path for v1" reasoning stays
historically accurate and is not rewritten; only the mapping itself is
replaced).

## Context

ADR 0004 hardcoded `push_to_tracker`'s field list to the author's own
Notion database: `Status`, `Fit Rating`, and `Key Notes`, by exact
property name, with Python constants (`STATUS_PROPERTY`,
`FIT_RATING_PROPERTY`, `KEY_NOTES_PROPERTY` in `mapping.py`) as the only
source of truth. That ADR named this an explicit, tracked shortcut — "a
later phase will replace the hardcoded mapping with a configurable field
list ... treat the field list itself as arbitrary and user-defined" —
not the intended end state.

Two things depended on that hardcoded mapping and needed to change
together, not independently: `push_to_tracker`'s write path
(`NotionTrackingStore.record_analysis`) and the read path
(`get_analysis`/`list_analyses`, which `list_applications` calls). A
schema that only drove writes would leave reads silently broken the
moment a user's property names differed from the author's — the same
"easy miss" the read-path gap identified during design review of this
phase.

## Decision

### The schema

A `TrackingSchema` (`tracking_store/schema.py`), loaded once at server
startup from a YAML file (`TRACKING_SCHEMA_PATH`, default
`./tracking_schema.yaml`; accepts absolute and `~`-relative paths, not
assumed repo-relative), declares every field the user's tracker has:

- **`manual: true`** — the tool never reads or writes this field
  (company, comp range, source, work arrangement, ...). Declared for
  documentation only.
- **`derived_from: <status_fixed | fit_rating_from_bucket | key_notes>`**
  — a tool-populated field. `derived_from` is a closed vocabulary: the
  three values are the only things a `FitVerdict` can currently be
  turned into (`mapping.py`'s `_DERIVED_VALUE_BUILDERS`). This isn't
  configurable — the schema says *which* of the three a user's tracker
  wants and *where* to put it, not how to compute it.

Each field's storage location is backend-specific and optional per
backend: `notion.property` (+ `notion.type`, since a Notion property's
write payload shape differs by select/rich_text/etc.) and
`sqlite.column`. `SQLiteTrackingStore` only tracks fields with a
`sqlite.column` at all — it has no concept of Notion's manual,
pre-existing-row fields, so a field with only a `notion` section is
simply invisible to the SQLite backend, not an error.

`tracking_schema.example.yaml` (checked in) mirrors the author's real
14-field Notion tracker as a concrete template.
`tracking_schema.yaml` (the real, personal file) is gitignored, the same
pattern as `.env`/`.env.example`.

### Two validation tiers

- **Structural (hard failure, at load time)** — the schema file is
  missing/unreadable, isn't valid YAML, a field is missing `key`, a
  `key` is reused, a field is neither `manual: true` nor has a
  `derived_from`, or a `sqlite.column` isn't a safe SQL identifier
  (interpolated directly into SQL — column names can't be bound as query
  parameters). These mean the schema itself can't be used at all.
- **Per-field (warn-and-skip, at write time)** — an unrecognized
  `derived_from`, an unsupported `notion.type`, or (checked against the
  live Notion database, not just the local YAML) a `notion.property`
  that doesn't exist there. These are isolated misconfigurations: the
  rest of the write proceeds, the bad field is left out, and a warning
  explaining why is both logged and returned to the caller in
  `push_to_tracker`'s `warnings`. A single typo in one field's config
  shouldn't block every other field from being recorded.

`dry_run=True` only surfaces the first tier of per-field warnings
(bad `derived_from`/`notion.type`) — it makes no Notion API call, so it
can't check whether a `notion.property` actually exists on the live
database. That check only happens, and only surfaces in `warnings`, on
a real write.

### Read path follows the same schema

`NotionTrackingStore.get_analysis`/`list_analyses` resolve property names
and types from the schema's tool-populated fields, the same as the write
path, and key their result dicts by the schema's field `key` (e.g.
`status`, `fit_rating`, `notes`) rather than the Notion property name.
Without this, a user who renamed `Fit Rating` to something else in their
own schema would have `push_to_tracker` write correctly but
`list_applications` silently return `None` for that field forever,
without any error — the read path has to move in lockstep with the
write path for the same field list, not trail behind it.

### `status_fixed` carries forward Phase 3's assumption, unchanged

`push_to_tracker` still only ever sets `Status` once, to a constant
(`STATUS_VALUE`, "Not yet applied"), at analysis time. Every later
transition (Applied, Interviewing, Rejected, ...) is a manual edit in
Notion; the tool never reads it back to reconcile or re-derive anything.
This is why `list_applications(status?)` is still trustworthy despite
that: it reads live from the Notion API on every call, not from any
tool-side ledger of what it last wrote, so whatever's been hand-edited in
Notion is exactly what comes back.

## Consequences

- Someone with a different Notion schema, or a much simpler one (just
  `status`/`fit_rating`/`notes`, or even fewer), can use `push_to_tracker`
  and `list_applications` by editing `tracking_schema.yaml` alone — no
  code changes, no fork.
- `SQLiteTrackingStore`'s table columns are now derived from the schema
  at construction time instead of a fixed 3-column table; its result
  dicts are keyed by field `key`, matching Notion's shape.
- `mapping.py`'s constants (`STATUS_PROPERTY`, `FIT_RATING_PROPERTY`,
  `KEY_NOTES_PROPERTY`) are gone — anything that referenced them (or
  assumed those exact Notion property names) needs the schema instead.
- The warn-and-skip tier means a `push_to_tracker` call can partially
  succeed: some fields written, others silently (but loudly, via
  `warnings`) skipped. Callers that assumed "no exception thrown = every
  field written" need to check `warnings`, not just the absence of an
  error.
- `derived_from`'s closed vocabulary is still hardcoded Python
  (`mapping.py`) — adding a fourth computed field (e.g. a
  `retrieval_score`-derived one) still requires a code change, just not
  a change to *where in Notion* it goes. This ADR doesn't attempt to make
  the set of computable fields itself user-extensible.
