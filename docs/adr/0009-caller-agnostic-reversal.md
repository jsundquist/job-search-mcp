# 0009: Caller-agnostic reversal — fit judgment moves inside the server

## Status

Accepted. Reverses the "match_job stays evidence-only" decision described in
the Status section of `docs/job_fit_scoring_algorithm.md`.

## Context

That original decision — no internal LLM call, no new tool, `match_job`
retrieval-only, with the 5-layer rubric "applied manually (in-conversation,
by whichever assistant reads `match_job`'s retrieved evidence)" — was made
inline while building the rubric and validating it against real postings.
It was never written up as its own ADR; this is the first formal record of
that reasoning, and it is being superseded here rather than merely
documented after the fact.

The original reasoning held as long as the only assumed caller was an
LLM-driven assistant (Claude, Claude Code) with the rubric resource
(`job-fit://rubric`) in its context and the judgment to apply it
correctly. That assumption doesn't hold for an MCP server in general.
`job-search-mcp` is invoked over the standard MCP protocol, which makes no
guarantee about what's on the other end of a tool call:

- A caller may have no LLM in the loop at all — a scripted pipeline, a
  cron job, a non-agentic integration — and simply cannot "reason over the
  retrieved evidence" the way the design assumed.
- A caller may be a different LLM/assistant that never reads or is told to
  apply `job-fit://rubric`, and has no way to know the rubric exists or
  that `retrieval_score` is non-authoritative for fit (the exact
  misreading `retrieval_score`'s naming was already changed once to guard
  against — see `docs/adr/0008-resume-chunking-strategy.md` and
  `match_job.py`'s module docstring).
- Even a well-behaved LLM caller applying the rubric correctly will produce
  judgment that varies run to run and caller to caller, for a task
  (fit bucket assignment) that this project wants to be a stable,
  reproducible property of the server's response — not an artifact of
  which assistant happened to call it and how carefully.

In short: "the caller reasons over retrieved evidence" pushes a
correctness-critical part of this project's stated purpose (accurate fit
judgment, not just retrieval) onto a process this server has no ability to
verify, prompt, or trust reads the rubric at all. That's a materially
different, weaker guarantee than a caller-agnostic MCP server should offer,
and it's what actually needs to change — not any specific validated
detail of the rubric itself.

## Decision

Fit judgment moves inside the server via a new tool, `evaluate_fit`, which
owns an internal Anthropic API call and returns a structured fit verdict
directly — no assumption that the caller has an LLM, has read
`job-fit://rubric`, or will apply it faithfully.

`match_job` is unchanged by this ADR: it remains retrieval-only, returning
`retrieval_score` and `retrieved_chunks` as evidence, exactly as decided
in `docs/adr/0008-resume-chunking-strategy.md` and implemented in
`match_job.py`. `evaluate_fit` is additive, not a replacement — see
`docs/adr/0010-layer-split-design-evaluate-fit.md` for how it's split
internally and `docs/evaluate_fit_schema.md` for its finalized schema.

## Consequences

- The rubric (`docs/job_fit_scoring_algorithm.md`) stops being purely a
  resource for a caller to read and self-apply; part of it becomes logic
  the server executes and part of it becomes the contract for an internal
  LLM call. Its "Status" section, which describes the now-superseded
  evidence-only decision, should be treated as historical once
  `evaluate_fit` ships, not as the current state of the project.
- `job-search-mcp` takes on a new dependency: an internal Anthropic API
  call from within `evaluate_fit`, with its own credentials, latency, and
  failure modes (see the explicit failure contract in
  `docs/evaluate_fit_schema.md`). This is a real increase in the server's
  operational surface compared to the pure-retrieval original design, and
  is accepted deliberately in exchange for a caller-agnostic guarantee.
  Implementing that call is explicitly out of scope for this phase.
- Any future caller-facing feature that currently assumes "the calling
  assistant will read the rubric and apply it" should be re-examined
  against this same caller-agnostic requirement rather than repeating the
  original inline pattern.
