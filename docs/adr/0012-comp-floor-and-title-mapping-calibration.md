# 0012: Comp-floor check and title-mapping calibration for evaluate_fit

## Status

Accepted. Depends on `docs/adr/0009-caller-agnostic-reversal.md` and
`docs/adr/0010-layer-split-design-evaluate-fit.md`, and follows the
config-file pattern established by
`docs/adr/0011-configurable-tracking-field-schema.md`. Adds a sixth layer
(comp floor) to the deterministic/LLM split from ADR 0010, narrows Layer
5's red-flag scope slightly to avoid double-counting with the new layer,
and introduces a new gitignored per-candidate config file,
`candidate_profile.yaml`.

## Context

A retrospective report — a Claude session recalling, in prose, how it
manually evaluated roughly 70 postings over one week against the
5-layer rubric — surfaced two gaps not covered by the original rubric or
its ADR 0010 layer split:

1. **No comp-floor check exists anywhere.** Postings were reportedly
   demoted, in that manual process, when the stated comp ceiling fell
   below the candidate's target compensation floor — but there is
   currently no field, layer, or config value for this anywhere in the
   rubric, schema, or code (`FitVerdict` in `fit_verdict.py` has no comp
   field at all).
2. **Title-level mismatches need per-candidate calibration, not a Layer 3
   logic change.** A concrete case: a candidate whose prior employer had
   no "Staff" level meant their "Principal" title actually maps closer to
   industry-standard "Staff." Scored literally against title strings
   alone, Layer 3 would misjudge this as a seniority mismatch even though
   comp and scope both checked out. This isn't a flaw in Layer 3's logic
   — it's missing calibration context specific to one candidate's resume.

**On the strength of this evidence:** the "~70 postings over a week"
report is the source for both gaps above, but it is **unverified and
currently unverifiable**. A direct check (via transcript-search over this
machine's session history) found no independent record of those 70
postings anywhere — no company names, no prior session transcripts, no
tracked outcomes. The claim exists only as prose in the requests that
produced this ADR, dated the same day this ADR was written. This is a
materially weaker evidentiary basis than the 4 postings ADR 0010
validated against (Hims AI Tooling, Hims Customer Platform, 1Password
SDLC Foundations, Maven Clinic), which are individually named and
traceable. This ADR's design choices below should be read as **reasonable
hypotheses worth encoding**, not as validated the way the original
4-posting set was — see "Validation" below for what can and cannot
currently be claimed.

There is also, as of this ADR, no candidate-preference storage anywhere
in the codebase — the same gap already exists, undocumented, for Layer
4's "remote preferred, open to hybrid" preference, which has only ever
been prose in `docs/job_fit_scoring_algorithm.md`, never structured
config. This ADR closes that gap for comp floor and title-mapping
specifically (not for Layer 4's location preference, which stays out of
scope here) by introducing a general-purpose config file rather than
one-off values, so future per-candidate calibration needs have a home
without a new ADR each time.

## Decision

### Layer 6 — comp floor check (new deterministic layer)

Added to `docs/job_fit_scoring_algorithm.md` as Layer 6, alongside Layer 1
and Layer 4 as a deterministic, non-LLM check. Produces `comp_floor_check`
in `evaluate_fit`'s output:

```json
{
  "meets_floor": "boolean",
  "target_floor": "number",
  "posting_ceiling": "number | null",
  "category": "no penalty | small penalty | moderate-to-large penalty | gate-like",
  "rationale": "string"
}
```

`category` **reuses Layer 4's existing four-tier severity enum verbatim**
rather than a bespoke one. ADR 0010 already established a uniform
+1-per-triggered-layer demotion pattern specifically so that adding a
layer doesn't require inventing new arithmetic, and reusing the enum
keeps `comp_floor_check` auditable against the same rule everyone already
reads for `preference_severity`. A bespoke enum (e.g. a raw numeric gap
percentage) would be more precise but would require its own separate
demotion-mapping rule, which contradicts the "keep every layer legible
against the same table" goal ADR 0010 states as its reason for existing.

Tiering, with a concrete cutoff rather than a vague "close vs. well
under" distinction:

- Ceiling >= `target_floor` → `no penalty`, `meets_floor: true`.
- Ceiling under `target_floor` by up to 10% → `small penalty`.
- Ceiling more than 10% under `target_floor` → `moderate-to-large
  penalty`.
- No comp listed on the posting at all (`posting_ceiling: null`) →
  `moderate-to-large penalty`, `meets_floor: false` — an unverifiable
  floor is treated the same as "well under," not given the benefit of the
  doubt.
- `gate-like` is part of the enum for consistency but is **not currently
  assigned by any rule above** — reserved for a future, more extreme case
  (e.g. a ceiling far enough under the floor to be treated as a
  non-starter). Nothing in the current design requires it to be reachable
  yet.

The 10% cutoff is a starting number chosen for concreteness — it is not
independently validated against real postings (see "Validation" below)
and should be revisited once real, traceable data exists.

Demotion contribution follows ADR 0010's existing rule exactly: `no
penalty`/`small penalty` → 0 demotions; `moderate-to-large penalty` → 1;
`gate-like` → 1 (and caps the bucket at Possible Fit, same as any other
`gate-like` deterministic-layer result). No new demotion arithmetic is
introduced.

**Layer 5 overlap, resolved.** Layer 5's red-flag list already includes
"comp ambiguity." Left unqualified, a posting with no comp listed could
be demoted twice for the same underlying fact — once as a Layer 5 red
flag, once as a Layer 6 `moderate-to-large penalty`. Layer 5's scope is
narrowed to exclude "no comp listed at all" (now owned exclusively by
Layer 6); "comp ambiguity" in Layer 5 is reserved for vague or evasive
comp language that still isn't silence — "competitive salary" with no
number, an implausibly wide range, and similar.

**Comp comparability is out of scope.** `target_floor` is assumed to be a
single number in the same units/structure a posting's comp range is
expected to use (e.g. annual total target comp). Reconciling mismatched
structures — hourly contract rates, equity-heavy offers, base-only vs.
base+bonus postings — is not handled by this design. This is a known
limitation, not an oversight to be silently assumed away.

### `target_floor` provenance — closed by `candidate_profile.yaml`, not by a tool-input parameter

Unlike Layer 4's still-open location-preference gap, `target_floor`'s
provenance *is* addressed by this ADR: it lives in a new config file,
`candidate_profile.yaml`, alongside `title_mapping_note` (see below).

### Title-mapping calibration: new config value, not tool input

`title_mapping_note` (a free-text string) is read from
`candidate_profile.yaml`, threaded into the internal LLM call's prompt
context for **Layer 3 only**, instructing the model to weigh title-level
mismatches lightly when the note explains them and comp/scope otherwise
check out. It is not part of the LLM-facing *output* schema
(`domain_match`, `scope_match`, `red_flags`, `rationale`) — it is input
context that informs how `scope_match` is judged, not a field the LLM
produces or that gets validated.

An earlier draft of this design proposed `title_mapping_note` as a
per-call `evaluate_fit` tool-input parameter. That is explicitly rejected
here: it works against the caller-agnostic principle in
`docs/adr/0009-caller-agnostic-reversal.md`. This value is a stable
per-candidate fact, not something a caller should need to know about and
supply on every single call — doing so would reintroduce exactly the
kind of caller-side burden ADR 0009 moved away from, just for title
calibration instead of the whole rubric.

### Candidate profile config

Both `target_floor` and `title_mapping_note` live in a new file,
`candidate_profile.yaml`, read once at server startup — the same pattern
ADR 0011 established for `tracking_schema.yaml`/`TRACKING_SCHEMA_PATH`,
and the existing `.env`/`.env.example` pattern:

- `candidate_profile.yaml` (gitignored, personal — analogous to
  `tracking_schema.yaml`, which also does not exist in this checkout) is
  the real file, loaded from a path controlled by a new env var,
  `CANDIDATE_PROFILE_PATH`, defaulting to `./candidate_profile.yaml` if
  unset. Accepts absolute and `~`-relative paths, same as
  `TRACKING_SCHEMA_PATH`.
- `candidate_profile.example.yaml` (checked in) is the template, with
  placeholder values and a comment header, mirroring
  `tracking_schema.example.yaml`.

This file is documented as the **general home for future per-candidate
calibration values**, not a two-field one-off — e.g. a future location
preference (closing the Layer 4 gap noted in Context above) would belong
here too, without a new ADR just to add a field to an existing config
file.

**Missing-config failure policy.** `candidate_profile.yaml` (and a
`target_floor` value within it) is **required** for `evaluate_fit` to run
Layer 6 — a missing file or missing `target_floor` is a startup-time hard
failure, the same structural-failure tier ADR 0011 gave a missing/invalid
`tracking_schema.yaml`, not a silent skip of `comp_floor_check`. Every
other deterministic field (`gate_failures`, `preference_severity`) is
always present in a successful response, never omitted; `comp_floor_check`
follows the same "always present, or the tool explicitly errors before
producing any verdict" contract rather than becoming the first field
that's sometimes just missing. Implementing this startup validation is
out of scope for this ADR (documentation-only, same as ADR 0009 scoped
out implementing its internal LLM call) — but the contract itself is
decided here, not left open for an implementer to guess at.

### An explicit asymmetry between the two additions

These two calibration values are **not equally rigorous** and should not
be presented as such anywhere in the docs:

- **`target_floor` → Layer 6 (`comp_floor_check`) is a hard, deterministic,
  numeric comparison** — same rigor class as Layer 1 (gate failures) and
  Layer 4 (logistics severity). It runs in server code, not the LLM call,
  and its `category` participates in the demotion count exactly like any
  other deterministic layer.
- **`title_mapping_note` → Layer 3 is a soft, qualitative instruction fed
  into LLM judgment** — closer to a footnote appended to the prompt than
  a rule. It has no enum, no `category`, no direct demotion contribution
  of its own; it only ever shapes how `scope_match.category` gets judged,
  the same as any other piece of context the LLM already reads. It is
  advisory, not authoritative, and the LLM is free to weigh it against
  conflicting evidence in the JD/resume rather than apply it mechanically.

This asymmetry follows directly from ADR 0010's original split: numeric,
parseable comparisons are deterministic server logic; domain/scope/red-flag
judgment stays with the LLM. `title_mapping_note` doesn't change that
split — it's additional input *to* the LLM side of it, not a new
deterministic check.

### Bucket table: unchanged

The `demotion_count` → bucket table in ADR 0010 is not modified by this
ADR. The demotion-count model is additive and layer-count-agnostic: each
layer independently contributes 0 or 1 based on its own category, with no
dependency on how many layers exist, and `demotion_count`'s only
open-ended tier ("3+") already accommodates a demotion count above what 5
layers could produce. The only place a 6th layer could interact with the
table is the `demotion_count == 0` Good Fit/Strong Fit split, which
additionally reads `domain_match`/`scope_match` — `comp_floor_check`
touches neither field, so it cannot affect that split. This matches ADR
0010's own stated design intent: "a future revisit of the weighting table
above only requires changing the per-layer demotion mapping, not the
response shape."

## Validation

**Validation check performed. Result: no independently-checkable outcomes
exist for the 70-posting report; the comp-floor and title-mapping designs
below are unvalidated.** This is stated explicitly, as its own section,
rather than left implicit in the Decision text above, because it
determines the evidentiary weight the rest of this ADR can claim.

**What was checked.** Before accepting the retrospective report's
suggestions, a search was run over this machine's session-transcript
history (via the `transcript-search` MCP tool — semantic search across
indexed sessions, plus a keyword search specifically for "70 postings
week job search manual evaluation") to look for any independently
recoverable record of the ~70 postings referenced: company names, JD
text, session transcripts from the claimed week-long search, or bucket
ratings logged anywhere (e.g. in the tracking store) that could serve as
ground truth the way the original 4 postings did.

**Result.** No such record exists. The search returned no session
transcripts, no company names, and no tracked outcomes for any of the 70
postings. The only two places the "~70 postings over a week" claim
appears anywhere in this machine's session history are the literal text
of the two requests that produced this ADR — both sent the same day this
ADR was written. There is no prior session, no earlier date range, and no
external tracking record backing the claim. It cannot currently be
checked against independent ground truth, and no partial validation (even
against a handful of the 70) was possible for the same reason.

**Consequence for this ADR's design decisions.** ADR 0010 validated its
model against 4 individually-named, traceable postings (Hims AI Tooling,
Hims Customer Platform, 1Password SDLC Foundations, Maven Clinic). This
ADR has no equivalent evidentiary basis. Given that, this ADR does **not**
claim the comp-floor tiering (including the 10% cutoff) or the
title-mapping calibration approach are validated in the sense ADR 0010
used that word. They are reasonable designs that follow directly from ADR
0010's existing patterns (reuse the four-tier enum, uniform +1 demotion,
config-file-not-tool-input following ADR 0011's precedent), but they are
design decisions pending real test data, not confirmed findings. They
should be re-validated the same way ADR 0010 flagged its own unvalidated
cases (`gate-like`, `scope_match: low`, `red_flags` in isolation) for
re-validation once real postings are seen — Layer 6 and
`title_mapping_note`'s effect on `scope_match` should be added to that
same "re-validate once real postings hit them" list, not treated as
settled.

Separately: the 4 originally-validated postings from ADR 0010 were rated
before Layer 6 existed. If any of them lacked a stated comp range, adding
Layer 6 could in principle change their computed bucket under the new
model. Re-validating those 4 postings against Layer 6 is out of scope for
this (documentation-only) ADR, but is flagged here rather than silently
assumed away.

## Consequences

- `evaluate_fit`'s tool input schema (`job_description` + `source_url`)
  is unchanged by this ADR — the caller-agnostic property from ADR 0009
  is preserved exactly, with no new per-call parameters.
- `evaluate_fit` gains a new startup-time dependency: reading and
  validating `candidate_profile.yaml` (path from `CANDIDATE_PROFILE_PATH`,
  default `./candidate_profile.yaml`), the same operational shape as
  `TRACKING_SCHEMA_PATH` from ADR 0011, with a fail-closed contract (see
  "Missing-config failure policy" above) — a missing/invalid file is a
  startup-time failure, not a silently degraded response.
- Layer 5's red-flag scope is narrowed slightly (excludes "no comp listed
  at all," now owned by Layer 6) to avoid double-counting the same fact
  under two different layers.
- `FitVerdict` (`src/job_search_mcp/fit_verdict.py`) will need a
  `comp_floor_check`-shaped field added once implementation begins —
  noted here as a known follow-up, not implemented by this ADR, which is
  documentation-only.
- `docs/adr/0004-tracking-field-mapping-v1-shortcut.md` /
  `docs/adr/0011-configurable-tracking-field-schema.md`'s `Key Notes`
  concatenation (`rationale`, `gate_failures`, `red_flags`, `domain_match`,
  `scope_match`, `preference_severity`) will eventually want
  `comp_floor_check` added to that same writeup once `push_to_tracker` is
  updated — also out of scope here, flagged as a follow-up for whoever
  implements Layer 6.
- Because both the comp-floor tiering and the title-mapping-calibration
  approach rest on an unverifiable retrospective report rather than
  individually-validated postings, this design should be treated as more
  provisional than ADR 0010's — a stronger candidate for revision the
  first time real, traceable posting data disagrees with it.
