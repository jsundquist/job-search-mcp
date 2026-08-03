"""FitVerdict: evaluate_fit's tool output shape.

Defined here (rather than inside an `evaluate_fit` module) because
`evaluate_fit` itself is not implemented yet — see
docs/evaluate_fit_schema.md and docs/adr/0010-layer-split-design-evaluate-fit.md
for the finalized schema and bucket model this type mirrors. Consumers
that only need the output shape (e.g. push_to_tracker) can depend on this
without depending on evaluate_fit's (not-yet-existing) implementation.
"""

from __future__ import annotations

from typing import Literal, TypedDict

DomainScopeCategory = Literal["high", "medium", "low"]
PreferenceSeverityCategory = Literal[
    "no penalty", "small penalty", "moderate-to-large penalty", "gate-like"
]
Bucket = Literal["Strong Fit", "Good Fit", "Possible Fit", "Weak Fit", "Not a Fit"]


class CategoryJudgment(TypedDict):
    category: str
    rationale: str


class FitVerdict(TypedDict):
    gate_failures: list[str]
    domain_match: CategoryJudgment
    scope_match: CategoryJudgment
    preference_severity: CategoryJudgment
    red_flags: list[str]
    rationale: str
    demotion_count: int
    bucket: Bucket
