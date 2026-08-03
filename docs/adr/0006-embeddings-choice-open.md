# 0006: Embeddings choice

## Status

Proposed — open, not decided. Author input requested before finalizing.

## Context

Both the resume/experience corpus and incoming job descriptions need to be
turned into vectors before `VectorStore` (ADR 0002) can do similarity
search over them. Unlike the vector store, tracking store, and resume
source, embeddings generation doesn't yet have an obvious default: it sits
on a real tradeoff between running a model locally versus calling a hosted
embeddings API, and the right choice depends on priorities (cost, quality,
offline capability, setup complexity) that haven't been settled yet.

This ADR exists to lay out that tradeoff rather than to record a decision.
No embeddings implementation is scaffolded in this phase.

## Options

**Local — `sentence-transformers`**

- No API key, no per-call cost, works fully offline.
- Runs on the author's own hardware; quality and speed depend on the model
  chosen and available CPU/GPU. Smaller local models generally trail
  API-based models on retrieval quality.
- Adds a (potentially large) local dependency and model download.
- No data leaves the machine — relevant if resume content is considered
  sensitive.

**API-based — OpenAI or Voyage**

- Generally higher retrieval quality, especially for domain-specific text,
  with minimal setup beyond an API key.
- Requires network access and an API key; incurs per-call cost (small at
  this project's scale, but non-zero and ongoing).
- Resume and job description content is sent to a third-party API for
  embedding.
- No local compute or model management burden.

## Decision

Not yet made. To be finalized once the author weighs in on priority
between cost/offline-capability (favors local) and retrieval
quality/simplicity (favors API-based). This ADR should be updated to
"Accepted" with the chosen option once that input is given, and a
corresponding default implementation added under a new
`embeddings/` package following the same adapter pattern as ADR 0001.

## Consequences

Deferred until a decision is made.
