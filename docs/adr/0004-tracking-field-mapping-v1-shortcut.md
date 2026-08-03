# 0004: Tracking field mapping — v1 shortcut

## Status

Accepted (known limitation, not the intended end state)

## Context

`NotionTrackingStore` (ADR 0003) needs to translate a fit-analysis result
(whatever `match_job` eventually produces — expected to include at least
status, a fit rating, and free-text notes) into properties on the author's
specific Notion database. Building a general, user-configurable schema
mapping — letting any user declare their own Notion property names and
types for arbitrary analysis fields — is a meaningfully larger design and
implementation effort than the rest of this phase, and there is no second
user yet to design that generality against.

## Decision

For v1, `NotionTrackingStore` hardcodes a small, fixed mapping from
analysis output fields to the author's specific Notion database property
names (e.g. status, fit rating, notes). There is no configuration surface
for this mapping — it is Python code specific to one Notion database
schema.

### Concrete v1 mapping (implemented in `tracking_store/mapping.py`)

Only 3 of the author's many tracked Notion properties are touched by
`push_to_tracker`; every other property on an already-tracked row
(company, comp range, source, work arrangement, JD link, etc.) is left
as-is:

| evaluate_fit field | Notion property | Notion type | Mapping |
|---|---|---|---|
| (fixed) | `Status` | select | Always set to `"Not yet applied"` — evaluating fit doesn't imply any later status change (Applied, Recruiter screen, ...); those remain manual edits. |
| `bucket` | `Fit rating` | select | 1:1 by name against the author's 5-option select (`Strong Fit`, `Good Fit`, `Possible Fit`, `Weak Fit`, `Not A Fit`) and evaluate_fit's 5-value bucket enum (amended to 5 tiers by ADR 0010 specifically to make this 1:1 mapping possible — see that ADR for the Good Fit/Strong Fit split rule). Only capitalization of "Not A Fit" differs. |
| `rationale`, `gate_failures`, `red_flags`, `domain_match`, `scope_match`, `preference_severity` | `Key notes` | rich_text | Concatenated into one structured writeup: overall rationale, then itemized gate failures and red flags (if any), then each layer's category + rationale. |

`push_to_tracker` updates an existing tracked row by Notion page ID
(`job_id` *is* the page ID) — it never creates a new row or searches for
one by JD link. The author already adds a row when a job is first found;
this tool only fills in the fit-analysis columns on that existing row.

This is explicitly scoped as a shortcut that fits the author's current
setup only, not a design decision meant to generalize. It is documented
here specifically so it is not mistaken for the intended end state.

A later phase will replace the hardcoded mapping with a configurable field
list, most likely expressed in YAML, so that the set of fields — and their
names — is not assumed to be fixed at all. That later design should not
assume the current field set (status/fit rating/notes) is exhaustive or
correct; it should treat the field list itself as arbitrary and
user-defined.

## Consequences

- Fastest path to a working default `TrackingStore`, with no schema-design
  work blocking it.
- The mapping only works against the author's own Notion database as it
  exists today; any change to that database's properties, or any other
  user's differently-shaped database, breaks it.
- This is a known, intentional piece of technical debt. It should be
  revisited before this project is presented as usable by anyone other
  than the author, and the YAML-configurable field list is the tracked
  follow-up (see README roadmap).
- The concrete v1 mapping above is an explicit, known v1 limitation, not
  the intended end state, exactly as this ADR originally scoped: it
  assumes the author's specific property names (`Status`, `Fit rating`,
  `Key notes`), the author's specific 5-option `Fit rating` select values,
  and the author's specific "update by page ID, never create" write
  model. None of that generalizes to a different Notion schema, a
  different set of status/rating options, or a workflow that doesn't
  pre-add a row before running fit analysis. Phase 5's YAML-configurable
  field list should treat all of this — property names, option values,
  and the create-vs-update behavior — as arbitrary and user-defined, not
  assume this v1 shape is exhaustive or correct.
