# 0015: Prompt-injection defense for `job_description` text

## Status

Accepted (documentation/design-constraint only — see Scope below).

## Verification of the originating anecdote

This ADR was prompted by a task doc citing a specific incident: a
Skylight/NARA job posting alleged to contain a prompt-injection payload
(a "cinnamon-roll-recipe canary"), during the same retrospective
week-long manual job search whose "~70 postings" claim ADR 0012 already
found unverifiable.

A `transcript-search` check was run against this claim — the same kind of
check ADR 0012 ran, and its Validation section documents the same
methodology — searching for the Skylight/NARA posting, the described
canary payload, and related terms. **Result: no independent record
exists.** The only hits are the task doc that raised the claim (pasted in
the session that produced this ADR) and unrelated session content — no
company name, no posting text, no session transcript predating the claim
itself. Per the same standard ADR 0012 applied: this is unverified and
currently unverifiable, not a confirmed incident.

**This ADR does not rest on that anecdote.** It rests on the general,
independently-true property of the input source described below.

## Context

`job_description` — the primary input to `match_job` today, and to
`evaluate_fit` once implemented — is text that will often be scraped or
pasted from the open web: job boards, company career pages, aggregators.
Any tool that feeds untrusted web text into an LLM call must assume that
text can eventually contain adversarial content: a canary/test phrase, a
hidden instruction, a jailbreak attempt, or an attempt to manipulate the
calling assistant into taking actions beyond what the tool call requests
(e.g. calling `push_to_tracker`, `find_or_create_application`, or
`update_status` against an attacker-chosen `job_id` or with
attacker-influenced content). This is a property of "text from the open
web," not a property of any one confirmed incident.

`evaluate_fit`'s internal Anthropic API call is not implemented yet
(`docs/adr/0009-caller-agnostic-reversal.md` explicitly scoped
implementing that call out of its phase; `docs/evaluate_fit_schema.md`
states "no implementation, no internal API call code" up front). This ADR
therefore sets a binding design requirement for whoever implements that
call next, rather than changing any code today.

## Decision

### The prompt must delimit `job_description` as data, not instructions

Whenever `evaluate_fit`'s internal LLM call is implemented, the prompt
construction must:

- Wrap `job_description` (and any other externally-sourced text, e.g. a
  fetched posting body if that's ever added) in an explicit data
  delimiter — e.g. XML-style tags (`<job_description>...</job_description>`)
  distinct from any tag used for instructions.
- Include an explicit system-level instruction that content inside that
  delimiter is data to analyze, never instructions to follow, regardless
  of what the text itself claims, requests, or asserts about the
  assistant's role or task.
- Not interpolate `job_description` into the same prompt region as the
  rubric/system instructions without that delimiting — i.e. no naive
  string-concatenation of untrusted text directly into an instruction
  block.

This applies specifically to the LLM-facing schema's Layers 2, 3, and 5
(`docs/evaluate_fit_schema.md`'s "LLM-facing schema" section) — the only
part of `evaluate_fit` that involves an LLM call at all; Layers 1, 4, and
6 are deterministic server logic and don't parse `job_description` via an
LLM.

### `red_flags` (Layer 5) should surface suspected injection attempts

Layer 5 (`docs/job_fit_scoring_algorithm.md`) is instructed, as part of
its existing red-flag judgment, to treat content that reads as an attempt
to inject instructions, manipulate the assistant's behavior, or embed a
canary/test string as a red flag item — surfaced through the existing
`red_flags: list[str]` field. No new `FitVerdict` field is introduced;
this reuses the existing mechanism rather than adding a dedicated
`injection_detected` field, since a suspected injection is exactly the
kind of "the posting itself is untrustworthy" signal Layer 5 already
exists to surface to the candidate.

### Scope: this ADR and prompt wording only

Explicitly out of scope, per the instruction that produced this ADR: no
broader defensive-prompting research effort, no new tooling (e.g. a
separate classifier pass), no changes to `match_job` (which has no
internal LLM call to protect — the calling assistant reasons over
retrieved evidence itself today, per ADR 0009's "Status (historical)"
section in `docs/job_fit_scoring_algorithm.md`). This is a personal
single-user tool; the defense here is proportionate to that, not to a
multi-tenant threat model.

## Consequences

- Whoever implements `evaluate_fit`'s internal LLM call must follow the
  delimiting requirement above as part of that implementation — this ADR
  is binding design guidance for that future work, not optional
  hardening to consider later.
- `docs/evaluate_fit_schema.md` and `docs/job_fit_scoring_algorithm.md`
  (Layer 5) are updated to state this requirement, the same way ADR 0012
  already amended Layer 5's scope for the comp-ambiguity/comp-floor
  overlap.
- The unconfirmed Skylight/NARA anecdote is not cited anywhere in this
  project's docs as a confirmed incident; if it is ever independently
  corroborated, this ADR can be updated to cite it as a concrete example
  rather than purely general reasoning.
