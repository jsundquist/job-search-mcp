# Job Fit Scoring Algorithm

## Why retrieval_score fails

Cosine similarity over resume/JD embeddings measures surface lexical
overlap, not fit. Validated against 4 real postings: a consumer-growth JD
scored higher than a strong-fit platform JD because both mention
React/Node/TypeScript, even though the actual work is unrelated. A JD with
an explicit "Go required" line scored highest of all four, because the
score can't see that Go appears zero times in the resume. Keyword density
and categorical fit are different signals. `match_job`'s `retrieval_score`
should be treated as non-authoritative for bucket judgments — use the
retrieved chunks as evidence and apply the layered check below instead.

## Pipeline

1. Parse the JD into sections: required qualifications, preferred/nice-to-have
   qualifications, role description, logistics (location, comp, employment type).
2. Retrieve resume chunks via `match_job` as before — this stays useful for
   surfacing evidence, just not for scoring.
3. Run the five layers below (rules where possible, judgment where
   needed) to produce a demotion count and bucket.

**Process discipline:** score each layer independently from the JD/resume
evidence *before* looking at what bucket a posting "should" land in.
Reasoning backward from a known label (picking whichever layer's story
fits best) is confirmation bias and defeats the point of having separate
layers.

## Layer 1 — Hard requirement gates (pass/fail, checked first)

For each item listed under "required" (not "preferred"), check whether the
resume shows direct or clearly transferable evidence:

- Named languages/frameworks stated as required (e.g. "Proficiency in Go")
- Minimum years in a specific discipline (e.g. "8+ years backend")
- Degree requirements without an "or equivalent experience" clause
- Clearance, certification, or on-site/no-sponsorship constraints

A missing required item is a gate failure, not a partial deduction. Any
gate failure caps the result at "Possible Fit" at best, regardless of what
Layers 2-5 compute. Items listed only under "preferred" never gate — they
feed Layer 2 instead.

## Layer 2 — Domain / problem-space match

Classify the JD's actual problem domain, not its tech stack: internal
developer platform/tooling, consumer product growth engineering, backend
distributed infra, industry-specific product engineering (health, fintech,
etc.), SRE/DevOps, and so on. Classify the candidate's domain history the
same way. Score:

- Same domain → high
- Adjacent domain (e.g. general backend distributed systems) → medium
- Different domain that merely shares stack keywords (e.g. "full-stack,
  React, Node" on both a platform-tooling resume and a consumer
  growth-funnel JD) → low, even with strong lexical overlap

## Layer 3 — Role scope & seniority match

Compare stated title/level (Senior vs. Staff vs. Principal) and described
scope (owns architecture for a platform vs. contributes to a feature team)
against the candidate's actual level and scope. Check IC-track vs.
management-track framing against stated openness to both.

Layer 3 is also the one layer that reads per-candidate calibration
context: `title_mapping_note`, read from `candidate_profile.yaml` and
threaded into the internal LLM call's prompt for this layer only (see
`docs/evaluate_fit_schema.md`) — a free-text note the candidate supplies
once, up front, to correct for employer-specific title inflation or
deflation (e.g. "my last employer had no 'Staff' tier, so my 'Principal'
title maps closer to industry-standard 'Staff'"). This is qualitative
guidance fed into the LLM's judgment, not a rule the deterministic layers
apply — unlike Layer 6 below, there is no enum or demotion tier attached
to it directly; it only ever influences how `scope_match.category` gets
judged. See `docs/adr/0012-comp-floor-and-title-mapping-calibration.md`
for why this is config rather than a tool-input parameter, and for the
explicit rigor asymmetry between this and Layer 6.

## Layer 4 — Preference & logistics match

Stated preference is "remote preferred, open to hybrid" — so hybrid itself
never gates (Layer 1 stays reserved for capability/eligibility, not
logistics). Instead, grade the work-arrangement input on a severity scale,
since "hybrid" covers very different burdens:

- Remote → no penalty
- Hybrid, flexible/optional days → small penalty
- Hybrid, fixed mandatory cadence (e.g. "3x/week," or monthly in-person in
  a specific hub city) → moderate-to-large penalty — this can drive a
  posting down on its own
- Fully on-site, no remote option → treat as gate-like (caps the bucket) —
  this is the one arrangement actually outside "remote preferred, open to
  hybrid," not hybrid itself

Also covers: direct hire vs. contract-to-hire vs. contract, industry (open to any).

## Layer 5 — Red flags

Comp ambiguity, unclear reporting line, scope creep, degree requirement
with no equivalent-experience carve-out, excessive on-call/travel,
anything that reads as a bait-and-switch in the posting. "Comp ambiguity"
here means vague or evasive comp language (e.g. "competitive salary" with
no number, an implausibly wide range) — a posting that lists **no** comp
range at all is scored exclusively by Layer 6 below, not double-counted
here, to avoid demoting the same underlying fact twice.

Also covers suspected prompt injection: content in the posting that reads
as an attempt to inject instructions into the assistant's reasoning,
manipulate its behavior, or embed a canary/test string. `job_description`
is untrusted, often web-scraped text — see
`docs/adr/0015-prompt-injection-defense-for-job-description-text.md` for
the prompt-construction requirement this implies for the internal LLM
call, and why this is scored here rather than given a dedicated field.

## Layer 6 — Comp floor check

Deterministic, not LLM judgment — same category as Layer 1 and Layer 4.
Compares the posting's stated comp ceiling against the candidate's
`target_floor` (read from `candidate_profile.yaml` at server startup, not
supplied per-call — see `docs/evaluate_fit_schema.md`'s "Tool input"
section and `docs/adr/0012-comp-floor-and-title-mapping-calibration.md`
for why this is config, not a tool parameter).

- Posting's stated ceiling >= `target_floor` → no penalty
- Ceiling below `target_floor`, within 10% under → small penalty
- Ceiling more than 10% under `target_floor` → moderate-to-large penalty
- No comp listed at all, so the floor can't be verified → moderate-to-large
  penalty — treated the same as "well under," not as "no penalty by
  default." An unlisted range is not evidence the floor is met.

This reuses Layer 4's exact four-tier severity enum
(`no penalty | small penalty | moderate-to-large penalty | gate-like`) for
consistency with the rest of the demotion model, rather than a bespoke
enum. `gate-like` is available in the enum but is not currently assigned
by any rule above; it is reserved for a future case (e.g. a ceiling far
enough under the floor to be a non-starter outright), not triggered by
"no comp listed." The 10% cutoff is a starting number, not independently
validated — see
`docs/adr/0012-comp-floor-and-title-mapping-calibration.md`.

`target_floor` is assumed to be a single number in the same units/
structure a posting's comp range is expected to use (e.g. annual total
target comp, as documented explicitly in `candidate_profile.example.yaml`).
Full reconciliation of mismatched structures — hourly contract rates,
equity-heavy offers, base-only vs. base+bonus postings — is not handled
by this design; see the ADR for this limitation. Deterministic fallback
rules for common ambiguous cases:

- Zone/level-banded postings (a range tied to a level or geography rather
  than one stated ceiling): ambiguous, same tier as "no comp listed,"
  unless the stated level can be matched via `title_mapping_note`.
- Currency mismatches: convert if a reliable rate is available at
  evaluation time; otherwise ambiguous, same tier as above.
- Any comp structure other than the assumed one: ambiguous, same tier as
  above, if the posting doesn't clearly state which structure it uses.

See `docs/adr/0012-comp-floor-and-title-mapping-calibration.md` for the
full rationale.

## Bucket model

**Superseded.** This section originally specified a weighted-composite
model: a 0-100 weighted sum of Layers 2-5 (the ~40%/25%/20%/15% weights
that used to appear in the Layer 2-5 headers above), with the Layer 1 gate
capping the result. That model is retired — it was replaced by a
demotion-count model (each layer/gate contributes a uniform +1 demotion
when triggered, buckets read off the total) as part of the
`evaluate_fit` design. See
`docs/adr/0010-layer-split-design-evaluate-fit.md` for the full model,
per-layer demotion rules, and validation against the 4 known postings,
`docs/adr/0012-comp-floor-and-title-mapping-calibration.md` for the
Layer 6 (comp floor) addition and the title-mapping calibration input,
and `docs/evaluate_fit_schema.md` for the schema that implements both.
The old table below is kept only as a historical record of what was
replaced, not as a live scoring method:

| Bucket | Composite score (retired) |
|---|---|
| Strong Fit | 80-100, no gate failures |
| Possible Fit | 55-79, or 80-100 with a gate failure |
| Weak Fit | 30-54 |
| Not a Fit | below 30, or multiple gate failures |

## Implementation note

Output structured JSON, not just a number. `domain_match`/`scope_match` use
the strict `high | medium | low` enum from Layers 2/3 above;
`preference_severity` (not `preference_match`) uses the strict
`no penalty | small penalty | moderate-to-large penalty | gate-like` enum,
Layer 4's four severity tiers verbatim; `comp_floor_check` (Layer 6)
reuses the same four-tier enum for its own `category`; each is an object
with its own `category` and `rationale` rather than a single "category -
rationale" string, so category stays machine-checkable:

```json
{
  "gate_failures": ["Go required, not in resume"],
  "domain_match": {
    "category": "low",
    "rationale": "consumer growth engineering vs. internal platform tooling"
  },
  "scope_match": {
    "category": "high",
    "rationale": "Principal vs. Senior/Staff, comparable ownership"
  },
  "preference_severity": {
    "category": "moderate-to-large penalty",
    "rationale": "hybrid 3x/week vs. remote-preferred"
  },
  "comp_floor_check": {
    "meets_floor": false,
    "target_floor": 190000,
    "posting_ceiling": 175000,
    "category": "small penalty",
    "rationale": "posting ceiling $175k, ~8% under target floor $190k"
  },
  "red_flags": [],
  "bucket": "Possible Fit",
  "rationale": "..."
}
```

Note that `title_mapping_note` never appears in this output shape — it is
per-candidate context supplied to the internal LLM call for Layer 3, not
a judged field in its own right. See `docs/evaluate_fit_schema.md` and
`docs/adr/0012-comp-floor-and-title-mapping-calibration.md` for where it
lives and how it's threaded in.

Read the required-vs-preferred split, name the domain gap explicitly, and
let a gate failure override the raw similarity number. This is exactly the
shape `evaluate_fit` implements — see `docs/evaluate_fit_schema.md` for the
finalized, authoritative schema (including which fields come from
deterministic server logic vs. the internal LLM call, and how `bucket` is
computed from `demotion_count` rather than emitted directly).

## Status (historical)

**Superseded by `docs/adr/0009-caller-agnostic-reversal.md`.** The
paragraph below describes the original v1 decision — kept here as a
historical record, not as the current state of the project.

> This rubric is applied manually (in-conversation, by whichever assistant
> reads `match_job`'s retrieved evidence) — it is deliberately not built
> into `match_job` itself. `match_job` stays evidence-only: no internal LLM
> call, no new tool, retrieval only.

That decision was reversed: `match_job` remains retrieval-only, but a new
tool, `evaluate_fit`, now owns fit judgment via an internal Anthropic API
call plus deterministic server-side gate/logistics checks, so this rubric
is no longer applied only manually by whichever assistant happens to read
the retrieved evidence. See `docs/adr/0009-caller-agnostic-reversal.md`
for why, `docs/adr/0010-layer-split-design-evaluate-fit.md` for the
resulting layer split and bucket model, and
`docs/evaluate_fit_schema.md` for the finalized schema.

The rubric itself was validated retroactively against 4 real postings
(Hims AI Tooling = Strong Fit, Hims Customer Platform = Possible Fit via
low domain match, 1Password SDLC Foundations = Possible Fit via a Go gate
failure, Maven Clinic = Weak Fit via a gate failure plus a
hybrid-logistics penalty) — correctly separated all four buckets where
`retrieval_score` alone could not. This validation still holds; only the
"applied manually, not built into match_job" framing above is superseded.
