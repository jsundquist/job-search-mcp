# evaluate_fit — finalized schema

Schema only. No implementation, no gate-checking code, no internal API call
code — see `docs/adr/0009-caller-agnostic-reversal.md` and
`docs/adr/0010-layer-split-design-evaluate-fit.md` for the design decisions
this schema implements.

## Tool input

Same shape `match_job` already takes — this project has one resume corpus
per deployment (ingested via the existing `ResumeSource`/`VectorStore`
adapters, ADR 0001), addressed implicitly through the shared vector store
rather than a per-call resume selector. `evaluate_fit` does not introduce a
new way to reference a resume; it reuses retrieval exactly as `match_job`
does today.

```json
{
  "job_description": "string, required — full JD text",
  "source_url": "string | null, optional — where the JD was pulled from"
}
```

`evaluate_fit` also does not take per-candidate calibration values
(target compensation floor, title-mapping notes) as tool input — those
are stable across calls, not per-invocation, and passing them on every
call would work against the caller-agnostic design in
`docs/adr/0009-caller-agnostic-reversal.md`. They instead live in a
gitignored `candidate_profile.yaml`, read once at server startup — see
`docs/adr/0012-comp-floor-and-title-mapping-calibration.md`.

## Tool output

The full response `evaluate_fit` returns to any caller. `gate_failures`,
`preference_severity`, and `comp_floor_check` are populated by
deterministic server logic (Layer 1, Layer 4, and Layer 6 respectively —
see `docs/adr/0012-comp-floor-and-title-mapping-calibration.md` for why
Layer 6 is deterministic rather than LLM-judged); `domain_match`,
`scope_match`, and `red_flags` come from the internal LLM call (validated
against the LLM-facing schema below, with `title_mapping_note` from
`candidate_profile.yaml` supplied as prompt context for `scope_match`
specifically — it is never itself part of the LLM-facing schema) and are
passed through unchanged; `bucket` and `demotion_count` are computed
server-side after all three deterministic fields and the LLM output are
available and are never produced by the LLM call directly.

```json
{
  "gate_failures": ["string, ...  — e.g. \"Go required, not in resume\""],
  "domain_match": {
    "category": "high | medium | low",
    "rationale": "string"
  },
  "scope_match": {
    "category": "high | medium | low",
    "rationale": "string"
  },
  "preference_severity": {
    "category": "no penalty | small penalty | moderate-to-large penalty | gate-like",
    "rationale": "string"
  },
  "comp_floor_check": {
    "meets_floor": "boolean",
    "target_floor": "number",
    "posting_ceiling": "number | null",
    "category": "no penalty | small penalty | moderate-to-large penalty | gate-like",
    "rationale": "string"
  },
  "red_flags": ["string, ..."],
  "rationale": "string — overall summary tying the layers together",
  "demotion_count": "integer >= 0, server-computed",
  "bucket": "Strong Fit | Good Fit | Possible Fit | Weak Fit | Not a Fit, server-computed"
}
```

Field notes:

- `gate_failures`: empty array, not omitted, when no required item is
  missing.
- `domain_match.category` / `scope_match.category`: strict enum
  `["high", "medium", "low"]`, per Layer 2/3 of
  `docs/job_fit_scoring_algorithm.md`.
- `preference_severity.category`: strict enum
  `["no penalty", "small penalty", "moderate-to-large penalty", "gate-like"]`,
  matching Layer 4's four severity tiers verbatim as written in
  `docs/job_fit_scoring_algorithm.md`.
- `comp_floor_check`: deterministic, server-side (Layer 6), same category
  as `gate_failures`/`preference_severity` — never produced by the LLM
  call, and never omitted from a successful response (same "always
  present, not sometimes missing" convention as `gate_failures`/
  `red_flags`; a missing/invalid `candidate_profile.yaml` or missing
  `target_floor` is a hard startup failure, not a reason to omit this
  field from individual responses — see
  `docs/adr/0012-comp-floor-and-title-mapping-calibration.md`).
  `target_floor` is read from `candidate_profile.yaml` at server startup
  (see "Tool input" above); `posting_ceiling` is parsed from the JD text
  and is `null` when the posting lists no comp range at all.
  `meets_floor` is `posting_ceiling >= target_floor`, `false` (not
  `null`) when `posting_ceiling` is `null` — an unlisted range never
  counts as meeting the floor. `comp_floor_check.category` reuses
  `preference_severity`'s exact enum
  `["no penalty", "small penalty", "moderate-to-large penalty", "gate-like"]`;
  see Layer 6 of `docs/job_fit_scoring_algorithm.md` for which tier each
  ceiling/floor relationship maps to.
- `red_flags`: empty array, not omitted, when none are found.
- `bucket` / `demotion_count`: never present in, or accepted from, the
  LLM-facing schema below — see the failure contract for why this
  separation matters.
- `bucket` is a strict 5-value enum. It is not a pure function of
  `demotion_count`: at `demotion_count == 0`, `domain_match.category` and
  `scope_match.category` (both `high` or `medium` at that count — a `low`
  on either implies a demotion) additionally decide between `Strong Fit`
  (both `high`) and `Good Fit` (otherwise). `demotion_count` of 1, 2, and
  3+ map to `Possible Fit`, `Weak Fit`, and `Not a Fit` respectively,
  unaffected by this split. See
  `docs/adr/0010-layer-split-design-evaluate-fit.md` for the full table
  and rationale. Layer 6 (`comp_floor_check`) does not participate in
  this `demotion_count == 0` split — only `domain_match`/`scope_match`
  do, unchanged by
  `docs/adr/0012-comp-floor-and-title-mapping-calibration.md`.

## LLM-facing schema (internal Anthropic call)

**Prompt-injection requirement.** `job_description` is untrusted, often
web-scraped text. The prompt construction for this call must wrap
`job_description` in an explicit data delimiter (e.g.
`<job_description>...</job_description>`), distinct from any
instruction/system text, with an explicit instruction that content inside
it is data to analyze, never instructions to follow, regardless of what
the text itself claims or requests. See
`docs/adr/0015-prompt-injection-defense-for-job-description-text.md`.

This is the schema the internal Anthropic API call's structured output is
validated against. It covers exactly the LLM-judgment layers (2, 3, 5) from
`docs/adr/0010-layer-split-design-evaluate-fit.md` — it does not include
`gate_failures` or `preference_severity` (deterministic, computed
separately in server code) and it does not include `bucket` or
`demotion_count` (computed server-side from the demotion count once all
layers are known — the LLM never sees or decides the bucket). It also
does not include `comp_floor_check` (deterministic, computed separately
in server code, same as `gate_failures`/`preference_severity` — see
`docs/adr/0012-comp-floor-and-title-mapping-calibration.md`).
`title_mapping_note`, read from `candidate_profile.yaml`, is supplied as
additional prompt context for this call (specifically for the
`scope_match` judgment) but is not itself a field in this schema — it
never appears in either the request-shaped context or the validated
output, only in the prompt text the server constructs.

```json
{
  "domain_match": {
    "category": "high | medium | low",
    "rationale": "string"
  },
  "scope_match": {
    "category": "high | medium | low",
    "rationale": "string"
  },
  "red_flags": ["string, ..."],
  "rationale": "string"
}
```

The full tool output is assembled server-side as:
`{gate_failures, preference_severity, comp_floor_check}` (deterministic)
merged with this validated LLM output, plus `demotion_count`/`bucket`
computed from all six layers per the table in
`docs/adr/0010-layer-split-design-evaluate-fit.md` (unchanged by the
Layer 6 addition — see
`docs/adr/0012-comp-floor-and-title-mapping-calibration.md`).

## Failure contract

If the internal Anthropic API call errors, times out, or returns output
that fails validation against the LLM-facing schema above, `evaluate_fit`
returns a distinct, explicit error result — it never falls back to a
partial verdict built from Layer 1/4/6 (`gate_failures` /
`preference_severity` / `comp_floor_check`) alone. A caller must never
receive something that looks like a complete fit verdict (in particular,
must never receive a `bucket`) when only the deterministic half of the
evaluation actually ran.
