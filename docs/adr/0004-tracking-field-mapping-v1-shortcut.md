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
