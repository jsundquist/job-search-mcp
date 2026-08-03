# Job Fit Scoring Algorithm

## Why retrieval_score fails

Cosine similarity over resume/JD embeddings measures surface lexical
overlap, not fit. Validated against 5 real postings: a consumer-growth JD
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
   needed) to produce a composite score and bucket.

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
Layers 2-4 compute. Items listed only under "preferred" never gate — they
feed Layer 2 instead.

## Layer 2 — Domain / problem-space match (weight ~40%)

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

## Layer 3 — Role scope & seniority match (weight ~25%)

Compare stated title/level (Senior vs. Staff vs. Principal) and described
scope (owns architecture for a platform vs. contributes to a feature team)
against the candidate's actual level and scope. Check IC-track vs.
management-track framing against stated openness to both.

## Layer 4 — Preference & logistics match (weight ~20%)

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

## Layer 5 — Red flags (weight ~15%, subtractive)

Comp ambiguity, unclear reporting line, scope creep, degree requirement
with no equivalent-experience carve-out, excessive on-call/travel,
anything that reads as a bait-and-switch in the posting.

## Composite score and buckets

Weighted sum of Layers 2-5 → 0-100 composite, then apply the Layer 1 gate cap.

| Bucket | Composite score |
|---|---|
| Strong Fit | 80-100, no gate failures |
| Possible Fit | 55-79, or 80-100 with a gate failure |
| Weak Fit | 30-54 |
| Not a Fit | below 30, or multiple gate failures |

## Implementation note

Output structured JSON, not just a number:

```json
{
  "gate_failures": ["Go required, not in resume"],
  "domain_match": "low - consumer growth engineering vs. internal platform tooling",
  "scope_match": "high - Principal vs. Senior/Staff, comparable ownership",
  "preference_match": "medium - hybrid 3x/week vs. remote-preferred",
  "red_flags": [],
  "bucket": "Possible Fit",
  "rationale": "..."
}
```

Read the required-vs-preferred split, name the domain gap explicitly, and
let a gate failure override the raw similarity number.

## Status

This rubric is applied manually (in-conversation, by whichever assistant
reads `match_job`'s retrieved evidence) — it is deliberately not built
into `match_job` itself. `match_job` stays evidence-only: no internal LLM
call, no new tool, retrieval only. Validated retroactively against 5 real
postings (Hims AI Tooling = Strong Fit, Hims Customer Platform = Possible
Fit via low domain match, 1Password SDLC Foundations = Possible Fit via a
Go gate failure, Maven Clinic = Weak Fit via a hybrid-logistics penalty) —
correctly separated all four buckets where `retrieval_score` alone could not.
