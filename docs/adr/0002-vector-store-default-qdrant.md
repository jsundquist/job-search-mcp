# 0002: Vector store default — Qdrant

## Status

Accepted

## Context

The `VectorStore` interface (ADR 0001) needs a default implementation. The
author works across two machines (Windows and Mac), and needs the vector
store to be reachable from both without maintaining a locally-running
service on each. Qdrant has a hosted Cloud offering with a straightforward
Python client, which fits that constraint directly.

Qdrant is not the only reasonable choice, and a hosted service is not the
only reasonable deployment model — someone without a cloud account
(or unwilling to pay for one) should be able to run Qdrant themselves in
Docker, or use a different vector database entirely, without the interface
needing to change.

## Decision

Ship `QdrantVectorStore` (`src/job_search_mcp/vector_store/qdrant_store.py`)
as the default `VectorStore` implementation, configured against Qdrant
Cloud for the author's own use — chosen specifically because it removes the
need to keep a service running and reachable on both a Windows machine and
a Mac.

The `VectorStore` interface itself is implementation-agnostic: nothing in
`base.py` assumes a hosted service. A self-hosted Qdrant-in-Docker
implementation is equally valid — it would still be a `QdrantVectorStore`
(or a close variant), just constructed with a local URL instead of a Cloud
one, since the Qdrant client speaks the same protocol either way. This is
noted here rather than deferred to a separate ADR because it is a
configuration difference, not a design decision — no interface change is
required to support it.

## Consequences

- The author gets a zero-maintenance vector store that works identically
  from either machine.
- Cloud usage implies a dependency on network access and (depending on
  plan) cost, which a self-hosted user would avoid.
- Anyone without a Qdrant Cloud account can point the same
  `QdrantVectorStore` implementation at a local Docker instance by changing
  only the connection URL/API key — no new implementation is required for
  that specific case.
- A genuinely different vector database (e.g. pgvector, Weaviate, Chroma)
  would require a new `VectorStore` implementation, but not any change to
  matching logic, per ADR 0001.
