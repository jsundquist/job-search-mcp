# 0010: Layer-split design for evaluate_fit — deterministic gates vs. LLM judgment, demotion-count buckets

## Status

Accepted. Depends on `docs/adr/0009-caller-agnostic-reversal.md`. Replaces
the weighted-composite scoring model described in the "Composite score and
buckets" section of `docs/job_fit_scoring_algorithm.md` with a
demotion-count model, for the portion of the rubric that moves inside
`evaluate_fit`.

Amended (still Accepted): the bucket enum is five-valued, not four. The
original four-bucket table collapsed every 0-demotion posting into a
single "Strong Fit" bucket, but the author's existing tracking system
distinguishes a plain-strong match from a genuinely exceptional one
("Good Fit" vs. "Strong Fit"). Rather than add a 5th demotion tier (which
would renumber 1/2/3+ and silently change the bucket of every
already-validated posting with 1+ demotions), the split is carved out of
the existing 0-demotion bucket only, using `domain_match`/`scope_match`
categories that are already computed and already known to be `high` or
`medium` whenever `demotion_count` is 0 (a `low` on either would itself
be a demotion). See the updated table below.

## Context

The rubric in `docs/job_fit_scoring_algorithm.md` has five layers. They
are not uniform in what kind of check they require:

- **Layer 1 (hard requirement gates)** and **Layer 4 (preference/logistics
  severity)** are checks against explicit, parseable JD text — "is Go
  listed under required qualifications," "is the work arrangement remote,
  hybrid-flexible, hybrid-fixed-cadence, or on-site" — compared against
  resume evidence or stated candidate preferences. These don't need
  judgment about domain or scope; they need reliable parsing and
  comparison, which deterministic server code does more cheaply and more
  reproducibly than an LLM call, and without the failure modes (timeout,
  malformed output, drift run to run) that come with one.
- **Layers 2 (domain match), 3 (scope/seniority match), and 5 (red
  flags)** require actual judgment: classifying a JD's problem domain and
  a candidate's domain history and deciding how well they align isn't a
  parsing problem, and neither is reading a posting for bait-and-switch
  signals. These stay LLM work.

The original composite model (weighted sum of Layers 2-5, 0-100, with a
Layer 1 gate cap) was designed before this split existed and doesn't map
cleanly onto "some layers are deterministic, some aren't" — a single
weighted score mixes a reproducible number with a judgment-derived one in
a way that makes it hard to tell, from the score alone, which part moved.
The demotion-count model replaces it for this reason: it keeps every
layer's contribution to the final bucket separately visible, rather than
folding everything into one composite number.

## Decision

### Split

`evaluate_fit` splits its work as follows:

- **Deterministic, server-side (no LLM call):**
  - Layer 1 — hard requirement gates. Produces `gate_failures`.
  - Layer 4 — preference/logistics severity. Produces `preference_severity`.
- **LLM judgment (internal Anthropic API call):**
  - Layer 2 — domain/problem-space match. Produces `domain_match`.
  - Layer 3 — role scope & seniority match. Produces `scope_match`.
  - Layer 5 — red flags. Produces `red_flags` (and contributes to the
    overall `rationale`).

The finalized request/response shapes for both the tool as a whole and the
internal LLM call are in `docs/evaluate_fit_schema.md`. This ADR covers
the design rationale and the bucket model; it does not specify
implementation.

### Demotion-count bucket model

Each layer contributes a whole number of "demotions" based on its result.
`demotion_count` is the sum across all layers, and the bucket is read off
a fixed table. For `demotion_count == 0`, a secondary rule splits the
bucket further using `domain_match`/`scope_match` (both are `high` or
`medium` whenever `demotion_count` is 0, since a `low` on either
contributes a demotion itself, per Layer 2/3 below):

| demotion_count | Bucket |
|---|---|
| 0, `domain_match` = high and `scope_match` = high | Strong Fit |
| 0, otherwise (either category is `medium`) | Good Fit |
| 1 | Possible Fit |
| 2 | Weak Fit |
| 3+ | Not a Fit |

`bucket` is therefore not a pure function of `demotion_count` alone at the
top of the scale — it also reads `domain_match.category` and
`scope_match.category` when `demotion_count` is 0. Every other tier (1, 2,
3+) is unaffected by this amendment and keeps the original, independently
validated demotion→bucket mapping below.

Per-layer demotion contribution:

- **Layer 1 (`gate_failures`):** 1 demotion per failed required item. A
  posting with two unmet required items is already at 2 demotions before
  any other layer is scored.
- **Layer 2 (`domain_match`):** category `low` → 1 demotion;
  `medium`/`high` → 0.
- **Layer 3 (`scope_match`):** category `low` → 1 demotion;
  `medium`/`high` → 0.
- **Layer 4 (`preference_severity`):** `no penalty`/`small penalty` → 0;
  `moderate-to-large penalty` → 1; `gate-like` → 1. Uniform with every
  other triggered layer — a single demotion per layer that fires, no
  per-severity-tier weighting inside Layer 4 itself. (See Maven Clinic
  below: reaching Weak Fit off logistics requires a second demotion from
  another layer, not a heavier weight on this one.)
- **Layer 5 (`red_flags`):** 1 demotion per item in the array.

Every triggered layer/gate contributes exactly 1 demotion — the model
deliberately has no per-layer weighting. This keeps `demotion_count`
legible as a plain count of "how many things were wrong," not a hidden
composite score wearing an integer's clothes.

### Validation against known ratings

This model reproduces all 4 previously-validated postings from
`docs/job_fit_scoring_algorithm.md`. The Good Fit/Strong Fit split only
applies at `demotion_count == 0`, so it only affects Hims AI Tooling here;
the other three postings' buckets are unchanged by this amendment since
none has `demotion_count == 0`:

| Posting | Demotions | Total | domain_match / scope_match | Bucket |
|---|---|---|---|---|
| Hims AI Tooling | none | 0 | high / high | Strong Fit |
| Hims Customer Platform | domain_match = low (1) | 1 | low / — | Possible Fit |
| 1Password SDLC Foundations | gate_failures: Go missing (1) | 1 | — / — | Possible Fit |
| Maven Clinic | gate_failures: degree requirement, no equivalent-experience clause (1); preference_severity = moderate-to-large penalty (1) | 2 | — / — | Weak Fit |

No known posting currently exercises the `demotion_count == 0` /
Good Fit split (a 0-demotion posting with a `medium` on either
`domain_match` or `scope_match`) — Hims AI Tooling is assumed `high`/`high`
since it was rated Strong Fit prior to this amendment, but that specific
pairing wasn't independently re-verified against the original JD/resume
evidence. Re-validate once a real 0-demotion, medium-category posting is
seen.

Maven Clinic is the case that exercises two demotions from two different
layers at once: a Layer 1 gate failure (a degree requirement with no
equivalent-experience carve-out — the exact Layer 1 example named in
`docs/job_fit_scoring_algorithm.md`) plus the Layer 4 hybrid-logistics
penalty. Under uniform +1 weighting neither alone reaches Weak Fit (each
is only Possible Fit on its own); it's the combination that lands there,
which is the intended behavior of a plain demotion count.

No known posting currently exercises 3+ demotions (Not a Fit) or the
`gate-like` / `scope_match: low` / `red_flags` contributions in
isolation — those are extrapolated from the rubric text and this design's
internal consistency, not independently validated yet. Re-validate against
those cases once real postings hit them.

## Consequences

- `evaluate_fit`'s output makes each layer's contribution to the bucket
  individually inspectable (`gate_failures`, `domain_match`, `scope_match`,
  `preference_severity`, `red_flags` each carry their own rationale) rather
  than collapsing into one opaque composite number — a caller or reviewer
  can see exactly which layer(s) demoted a posting, and there is no
  reserved capacity for a raw composite score field — a future revisit of
  the weighting table above only requires changing the per-layer demotion
  mapping, not the response shape.
- The LLM call only ever produces Layers 2/3/5; it never sees or decides
  `gate_failures` or `preference_severity`, and never computes
  `demotion_count` or the bucket itself — those are attached server-side
  after the LLM response validates. This keeps the reproducible parts of
  the verdict (gates, logistics, bucket arithmetic) fully deterministic
  even though the domain/scope/red-flag judgment is not.
- The uniform +1-per-triggered-layer weighting is a deliberate, thin-but-
  validated fit to 4 known postings, not a first-principles design. It
  works because none of the 4 known postings depends on treating any one
  layer as inherently worse than another — Maven Clinic reaches Weak Fit
  through two independently-triggered layers, not through one layer being
  weighted more heavily. If a future posting's demotion_count feels wrong
  against real judgment, revisit the uniform weighting before mistrusting
  the split itself.
- `bucket` is a strict 5-value enum (`Strong Fit`, `Good Fit`,
  `Possible Fit`, `Weak Fit`, `Not a Fit`), not a pure function of
  `demotion_count` — the Good Fit/Strong Fit split additionally reads
  `domain_match.category` and `scope_match.category` at
  `demotion_count == 0`. Any future consumer of `demotion_count` alone
  (rather than the computed `bucket`) must account for this, since
  `demotion_count == 0` no longer implies a single bucket.
