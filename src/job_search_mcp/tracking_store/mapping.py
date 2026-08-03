"""push_to_tracker's field mapping: FitVerdict -> the author's Notion properties.

Hardcoded, single-database mapping — not a configurable schema. See
docs/adr/0004-tracking-field-mapping-v1-shortcut.md: this is a known v1
shortcut, not the intended end state. A later phase replaces this with a
user-defined, YAML-configurable field list.

Only three of the author's many tracked Notion properties are touched
here (Status, Fit rating, Key notes) — every other property on an
existing row (company, comp range, source, work arrangement, etc.) is
left untouched by this mapping.
"""

from __future__ import annotations

from job_search_mcp.fit_verdict import FitVerdict

STATUS_PROPERTY = "Status"
FIT_RATING_PROPERTY = "Fit rating"
KEY_NOTES_PROPERTY = "Key notes"

# push_to_tracker only ever sets this one Status value: running a fit
# analysis means the job has now been evaluated (but not yet acted on).
# Every later status transition (Applied, Recruiter screen, ...) is a
# manual edit the author makes in Notion, not something this tool drives.
STATUS_VALUE = "Not yet applied"

# 1:1 by name against the author's 5-option Fit rating select
# (Strong Fit, Good Fit, Possible Fit, Weak Fit, Not A Fit) and
# evaluate_fit's 5-value bucket enum (docs/adr/0010, amended to 5 tiers).
# Only the capitalization of "not a fit" differs between the two.
FIT_RATING_BY_BUCKET: dict[str, str] = {
    "Strong Fit": "Strong Fit",
    "Good Fit": "Good Fit",
    "Possible Fit": "Possible Fit",
    "Weak Fit": "Weak Fit",
    "Not a Fit": "Not A Fit",
}


def map_bucket_to_fit_rating(bucket: str) -> str:
    try:
        return FIT_RATING_BY_BUCKET[bucket]
    except KeyError:
        raise ValueError(f"Unrecognized evaluate_fit bucket: {bucket!r}") from None


def build_key_notes(verdict: FitVerdict) -> str:
    """Structured writeup: rationale plus itemized gate failures and red flags."""
    lines = [verdict["rationale"]]

    if verdict["gate_failures"]:
        lines.append("")
        lines.append("Gate failures:")
        lines.extend(f"- {item}" for item in verdict["gate_failures"])

    if verdict["red_flags"]:
        lines.append("")
        lines.append("Red flags:")
        lines.extend(f"- {item}" for item in verdict["red_flags"])

    lines.append("")
    lines.append(f"Domain match ({verdict['domain_match']['category']}): {verdict['domain_match']['rationale']}")
    lines.append(f"Scope match ({verdict['scope_match']['category']}): {verdict['scope_match']['rationale']}")
    lines.append(
        f"Preference severity ({verdict['preference_severity']['category']}): "
        f"{verdict['preference_severity']['rationale']}"
    )

    return "\n".join(lines)


def build_notion_properties(verdict: FitVerdict) -> dict:
    """The Notion API `properties` payload for updating an existing tracked job."""
    return {
        STATUS_PROPERTY: {"select": {"name": STATUS_VALUE}},
        FIT_RATING_PROPERTY: {"select": {"name": map_bucket_to_fit_rating(verdict["bucket"])}},
        KEY_NOTES_PROPERTY: {"rich_text": [{"text": {"content": build_key_notes(verdict)}}]},
    }


def build_tracking_fields(verdict: FitVerdict) -> dict:
    """Backend-agnostic mapped fields, for stores (e.g. SQLite) that don't use Notion's property shape."""
    return {
        "status": STATUS_VALUE,
        "fit_rating": map_bucket_to_fit_rating(verdict["bucket"]),
        "notes": build_key_notes(verdict),
    }
