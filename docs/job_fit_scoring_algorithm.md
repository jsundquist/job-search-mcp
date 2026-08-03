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
anything that reads as a bait-and-switch in the posting.

## Bucket model

**Superseded.** This section originally specified a weighted-composite
model: a 0-100 weighted sum of Layers 2-5 (the ~40%/25%/20%/15% weights
that used to appear in the Layer 2-5 headers above), with the Layer 1 gate
capping the result. That model is retired — it was replaced by a
demotion-count model (each layer/gate contributes a uniform +1 demotion
when triggered, buckets read off the total) as part of the
`evaluate_fit` design. See
`docs/adr/0010-layer-split-design-evaluate-fit.md` for the full model,
per-layer demotion rules, and validation against the 4 known postings, and
`docs/evaluate_fit_schema.md` for the schema that implements it. The old
table below is kept only as a historical record of what was replaced, not
as a live scoring method:

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
Layer 4's four severity tiers verbatim; each is an object with its own
`category` and `rationale` rather than a single "category - rationale"
string, so category stays machine-checkable:

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
  "red_flags": [],
  "bucket": "Possible Fit",
  "rationale": "..."
}
```

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
