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

## Tool output

The full response `evaluate_fit` returns to any caller. `gate_failures` and
`preference_severity` are populated by deterministic server logic (Layer 1
and Layer 4); `domain_match`, `scope_match`, and `red_flags` come from the
internal LLM call (validated against the LLM-facing schema below) and are
passed through unchanged; `bucket` and `demotion_count` are computed
server-side after both are available and are never produced by the LLM
call directly.

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
  and rationale.

## LLM-facing schema (internal Anthropic call)

This is the schema the internal Anthropic API call's structured output is
validated against. It covers exactly the LLM-judgment layers (2, 3, 5) from
`docs/adr/0010-layer-split-design-evaluate-fit.md` — it does not include
`gate_failures` or `preference_severity` (deterministic, computed
separately in server code) and it does not include `bucket` or
`demotion_count` (computed server-side from the demotion count once all
layers are known — the LLM never sees or decides the bucket).

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
`{gate_failures, preference_severity}` (deterministic) merged with this
validated LLM output, plus `demotion_count`/`bucket` computed from all five
layers per the table in `docs/adr/0010-layer-split-design-evaluate-fit.md`.

## Failure contract

If the internal Anthropic API call errors, times out, or returns output
that fails validation against the LLM-facing schema above, `evaluate_fit`
returns a distinct, explicit error result — it never falls back to a
partial verdict built from Layer 1/4 (`gate_failures` /
`preference_severity`) alone. A caller must never receive something that
looks like a complete fit verdict (in particular, must never receive a
`bucket`) when only the deterministic half of the evaluation actually ran.
