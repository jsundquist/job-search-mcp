# 0007: Analysis-only for v1 — no resume generation

## Status

Accepted

## Context

Given a job description and a resume/experience corpus, it's tempting to
extend "analyze fit" into "generate a tailored resume/cover letter for this
job" — the same retrieved context could feed a generation step. Scoping
that in from the start would significantly widen what v1 needs to get
right: not just retrieval and matching quality, but the correctness,
tone, and trustworthiness of generated content that represents the author
to an employer.

## Decision

`job-search-mcp` v1 is scoped to retrieval, fit analysis, and tracking
only. It ingests a job description, retrieves relevant context from the
resume/experience corpus, and writes a fit analysis to a tracking store.
It does not generate, rewrite, or tailor resume content, and this is a
deliberate scope boundary rather than a missing feature to be filled in
immediately after v1.

Reasons:

- **Correctness/trust bar is much higher for generated content.** A wrong
  or misleading fit-rating is a minor annoyance to correct; a generated
  resume bullet that misstates the author's experience is a real risk to
  represent to an employer, and would need a much more careful
  review/verification step than this project currently provides.
- **Smaller adapter surface while the core is unproven.** The
  `VectorStore` / `TrackingStore` / `ResumeSource` adapters (ADR 0001) and
  the matching logic itself are new and unvalidated. Keeping scope to
  analysis lets that core get proven out before adding a generation
  feature with its own new requirements (e.g. output formatting, tone
  control, human review workflow).
- **Analysis and tracking are useful on their own.** Knowing fit and
  tracking status for a job doesn't require generating anything — this is
  a complete, independently useful v1, not a stub waiting on a bigger
  feature.

## Consequences

- No resume/cover-letter generation code, prompts, or output formatting
  exist in this project; adding them later is an intentionally separate,
  future decision, not an oversight to fix.
- Keeps the trust/verification burden of this project limited to "is this
  fit analysis accurate," not "is this generated content accurate and
  well-written."
- If resume generation is added later, it should be treated as a new
  feature with its own scoping and ADR, not a natural extension folded
  into existing matching logic.
