# 0017: Delimit `job_description` in `match_job`'s tool result

## Status

Accepted. Revises the `match_job` exclusion in
`docs/adr/0015-prompt-injection-defense-for-job-description-text.md`.

## Context

ADR 0015 mandated that `job_description` be wrapped in an explicit data
delimiter wherever it's handed to an LLM, but explicitly scoped that
requirement to `evaluate_fit`'s (not-yet-implemented) internal LLM call,
excluding `match_job` on the grounds that `match_job` "has no internal LLM
call to protect — the calling assistant reasons over retrieved evidence
itself today."

That exclusion missed that `match_job` still hands raw `job_description`
text to an LLM — just not one this server calls internally. `server.py`'s
`match_job` returns the full, unmodified `job_description` string as part
of its `TextContent`/`structured_content` tool result, and the calling
assistant reads that result as its next piece of context. From the
perspective of "is untrusted external text about to be read by an LLM,"
this is the same risk ADR 0015 already identified — the boundary is just
the MCP tool result instead of an internal prompt.

`evaluate_fit` still doesn't exist, so ADR 0015's original decision (bind
whoever implements that LLM call to the delimiting requirement) is
unchanged. This ADR only revises the `match_job` exclusion and adds the
reusable helper that requirement calls for.

## Decision

### `job_search_mcp.prompt_safety.delimit_untrusted_text`/`untrusted_text_block`

A small helper module (`src/job_search_mcp/prompt_safety.py`) implements
ADR 0015's delimiting requirement once, for reuse by both `match_job`
today and `evaluate_fit` whenever it's built:

- `delimit_untrusted_text(tag, text)` wraps `text` in `<tag>...</tag>`.
  `tag` is restricted to a plain identifier so it can't itself be used to
  fabricate a closing tag.
- `untrusted_text_block(tag, text)` adds the standard "treat this as data,
  not instructions" notice ADR 0015 calls for, and returns the whole thing
  as one string ready to hand to an LLM (as a prompt fragment or, as here,
  a tool result).

Both are best-effort signal to the reading LLM, not a hard sandboxing
boundary — `text` can still contain a literal `</tag>`-shaped string; no
plain-text delimiter fully prevents that. This is the same limitation ADR
0015 already implicitly accepted for its own recommended approach.

### `match_job` now returns a delimited copy of `job_description`

`server.py`'s `match_job` prepends a `TextContent` block built with
`untrusted_text_block("job_description", job_description)` before the
existing JSON `TextContent` block. The JSON block (and `structured_content`,
and the `FitAnalysis`/`build_fit_analysis` return value) are unchanged —
they still carry `job_description` raw, for any programmatic consumer that
needs the exact original string. Only the human/LLM-facing prose block is
new.

## Consequences

- `match_job`'s tool result now contains two `TextContent` items instead
  of one; MCP clients reading tool text should already handle multi-block
  content, so this isn't expected to break existing callers.
- `FitAnalysis`, `build_fit_analysis`, and `structured_content` are
  unchanged — no change to `match_job`'s programmatic output shape or the
  existing `tests/unit/test_match_job.py` assertions.
- `src/job_search_mcp/prompt_safety.py` exists now specifically so
  `evaluate_fit`'s future LLM call can reuse it rather than reimplementing
  ADR 0015's delimiting requirement from scratch.
