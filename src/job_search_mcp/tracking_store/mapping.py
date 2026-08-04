"""FitVerdict -> tracking-field value computation, and schema-driven payload building.

Phase 5 (docs/adr/0011-configurable-tracking-field-schema.md) replaced the
Phase 3 hardcoded field mapping (docs/adr/0004) with a user-declared
TrackingSchema (schema.py). What's fixed and non-configurable is *how*
each of the three known `derived_from` values is computed from a
FitVerdict — the schema only says which of them a user's tracker wants
(and under what property/column name), not how to compute them.
"""

from __future__ import annotations

from collections.abc import Callable

from job_search_mcp.fit_verdict import FitVerdict
from job_search_mcp.tracking_store.schema import TrackingField, TrackingSchema

# push_to_tracker only ever sets this one Status value: running a fit
# analysis means the job has now been evaluated (but not yet acted on).
# Every later status transition (Applied, Recruiter screen, ...) is a
# manual edit the author makes in Notion, not something this tool drives.
STATUS_VALUE = "Not yet applied"

# Identical strings against the author's Fit Rating select (which also has
# a "Not yet evaluated" option this tool never sets) and evaluate_fit's
# 5-value bucket enum (docs/adr/0010, amended to 5 tiers to make this
# mapping possible). Kept as an explicit table, not a passthrough, so an
# unrecognized bucket value fails loudly instead of writing garbage.
FIT_RATING_BY_BUCKET: dict[str, str] = {
    "Strong Fit": "Strong Fit",
    "Good Fit": "Good Fit",
    "Possible Fit": "Possible Fit",
    "Weak Fit": "Weak Fit",
    "Not a Fit": "Not a Fit",
}


class TrackingFieldConfigError(ValueError):
    """A schema field itself is misconfigured (bad derived_from or notion.type).

    Distinct from a plain ValueError a builder raises for bad *data* (e.g.
    map_bucket_to_fit_rating on a genuinely invalid bucket, which is a
    real bug upstream, not a misconfigured field) — callers catch only
    this type to decide what's safe to warn-and-skip versus what should
    still fail loudly. See build_notion_properties_from_schema and
    build_sqlite_fields_from_schema.
    """


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


# The fixed set of things a FitVerdict can be turned into. A schema
# field's `derived_from` naming anything outside this dict's keys is a
# per-field config error (see notion_store.py/sqlite_store.py's
# resolve_tool_populated_fields for the warn-and-skip handling of that).
_DERIVED_VALUE_BUILDERS: dict[str, Callable[[FitVerdict], str]] = {
    "status_fixed": lambda verdict: STATUS_VALUE,
    "fit_rating_from_bucket": lambda verdict: map_bucket_to_fit_rating(verdict["bucket"]),
    "key_notes": build_key_notes,
}


def compute_derived_value(derived_from: str, verdict: FitVerdict) -> str:
    """Compute a tool-populated field's value from a FitVerdict.

    Raises TrackingFieldConfigError for a `derived_from` outside the
    known set — the schema itself doesn't restrict this string, so an
    unrecognized value is only caught here, at the point something tries
    to act on it. A builder's own ValueError (bad *data*, not a bad
    field name) is not caught here and propagates as-is.
    """
    try:
        builder = _DERIVED_VALUE_BUILDERS[derived_from]
    except KeyError:
        raise TrackingFieldConfigError(f"Unrecognized derived_from: {derived_from!r}") from None
    return builder(verdict)


def notion_property_payload(notion_type: str, value: str) -> dict:
    if notion_type == "select":
        return {"select": {"name": value}}
    if notion_type == "rich_text":
        return {"rich_text": [{"text": {"content": value}}]}
    if notion_type == "title":
        return {"title": [{"text": {"content": value}}]}
    if notion_type == "url":
        return {"url": value}
    raise TrackingFieldConfigError(f"Unsupported notion.type: {notion_type!r}")


def build_notion_properties_from_schema(
    schema: TrackingSchema, verdict: FitVerdict, known_properties: dict | None = None
) -> tuple[dict, list[str]]:
    """The Notion API `properties` payload for a FitVerdict, per the user's schema.

    Only fields the schema marks tool-populated (`manual: false`, i.e. a
    `derived_from`) are considered — manual fields (company, comp range,
    source, work arrangement, etc.) are never touched.

    Returns (payload, warnings). A misconfigured field — an unrecognized
    `derived_from`, an unsupported `notion.type`, or (when
    `known_properties` is given, e.g. the live Notion database's actual
    property names) a `notion.property` that doesn't exist there — is
    warned about and left out of the payload rather than failing the
    whole write. `known_properties=None` skips that last check (used for
    the network-free dry_run preview, which can't see the live schema).
    """
    payload: dict = {}
    warnings: list[str] = []
    for field in schema.tool_populated_fields():
        if not field.notion_property:
            continue  # no Notion location declared for this field; nothing to write here
        if known_properties is not None and field.notion_property not in known_properties:
            warnings.append(
                f"Skipping tracking field {field.key!r}: Notion property "
                f"{field.notion_property!r} does not exist on the configured database."
            )
            continue
        try:
            value = compute_derived_value(field.derived_from, verdict)
            payload[field.notion_property] = notion_property_payload(field.notion_type, value)
        except TrackingFieldConfigError as exc:
            warnings.append(f"Skipping tracking field {field.key!r}: {exc}")
    return payload, warnings


def build_sqlite_fields_from_schema(schema: TrackingSchema, verdict: FitVerdict) -> tuple[dict[str, str], list[str]]:
    """Column-name -> value for the tool-populated fields SQLite tracks, plus warnings.

    Fields without a `sqlite.column` (fine for e.g. a Notion-only field
    the user's tracker has no SQLite equivalent for) are silently
    excluded, not written anywhere for that backend. A field with an
    unrecognized `derived_from` is warned about and skipped instead.
    """
    values: dict[str, str] = {}
    warnings: list[str] = []
    for field in schema.tool_populated_fields():
        if not field.sqlite_column:
            continue
        try:
            values[field.sqlite_column] = compute_derived_value(field.derived_from, verdict)
        except TrackingFieldConfigError as exc:
            warnings.append(f"Skipping tracking field {field.key!r}: {exc}")
    return values, warnings


def parse_notion_property(prop: dict, notion_type: str | None) -> str | None:
    """Read a tool-populated field's value back out of a Notion API page property."""
    if notion_type == "select":
        return (prop.get("select") or {}).get("name")
    if notion_type == "rich_text":
        return "".join(part.get("plain_text", "") for part in prop.get("rich_text") or [])
    if notion_type == "title":
        return "".join(part.get("plain_text", "") for part in prop.get("title") or [])
    if notion_type == "url":
        return prop.get("url")
    return None


def sqlite_tool_populated_fields(schema: TrackingSchema) -> list[TrackingField]:
    """Tool-populated fields SQLiteTrackingStore actually has a column for."""
    return [field for field in schema.tool_populated_fields() if field.sqlite_column]
