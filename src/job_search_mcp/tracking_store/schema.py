"""User-configurable tracking field schema.

Replaces the Phase 3 hardcoded field mapping
(docs/adr/0004-tracking-field-mapping-v1-shortcut.md) with a YAML-declared
field list, so a tracker with different property names — or a much
smaller set of fields — doesn't require editing code. See
docs/adr/0011-configurable-tracking-field-schema.md.

Only structural validity is checked here: the file parses, every field
entry is well-formed, and keys are unique. Whether an individual field's
`derived_from` is one of the values the matching logic can actually
produce, or its `notion.property` exists in the real Notion database, is
runtime/backend-dependent and is a per-field warn-and-skip concern for the
stores that consume this schema, not a reason to refuse to load it at
all — see tracking_store/notion_store.py and sqlite_store.py.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

# The only values a TrackingField's `derived_from` may name — the fixed
# set of things a FitVerdict can actually be turned into (see
# mapping.py's build_tracking_fields/build_notion_properties). Anything
# else is a per-field config error, not a code error.
KNOWN_DERIVED_SOURCES = frozenset({"status_fixed", "fit_rating_from_bucket", "key_notes"})


class TrackingSchemaError(Exception):
    """The schema file itself is missing, unreadable, or structurally invalid."""


@dataclass(frozen=True)
class TrackingField:
    key: str
    manual: bool
    derived_from: str | None = None
    notion_property: str | None = None
    notion_type: str | None = None
    sqlite_column: str | None = None


@dataclass(frozen=True)
class TrackingSchema:
    fields: list[TrackingField]

    def tool_populated_fields(self) -> list[TrackingField]:
        return [field for field in self.fields if not field.manual]


def load_tracking_schema(path: str | Path) -> TrackingSchema:
    """Load and structurally validate a tracking schema YAML file.

    Raises TrackingSchemaError if the file is missing, isn't valid YAML,
    or any field entry is malformed (missing `key`, a `key` reused by
    more than one entry, or neither `manual: true` nor a `derived_from`).
    """
    resolved = Path(path).expanduser()
    try:
        raw_text = resolved.read_text(encoding="utf-8")
    except OSError as exc:
        raise TrackingSchemaError(f"Could not read tracking schema at {resolved}: {exc}") from exc

    try:
        raw = yaml.safe_load(raw_text)
    except yaml.YAMLError as exc:
        raise TrackingSchemaError(f"Tracking schema at {resolved} is not valid YAML: {exc}") from exc

    if not isinstance(raw, dict) or not isinstance(raw.get("fields"), list) or not raw["fields"]:
        raise TrackingSchemaError(
            f"Tracking schema at {resolved} must have a top-level 'fields' list with at least one entry."
        )

    fields: list[TrackingField] = []
    seen_keys: set[str] = set()
    for entry in raw["fields"]:
        field = _parse_field(entry, resolved)
        if field.key in seen_keys:
            raise TrackingSchemaError(f"Tracking schema at {resolved} declares key {field.key!r} more than once.")
        seen_keys.add(field.key)
        fields.append(field)

    return TrackingSchema(fields=fields)


def _parse_field(entry: object, source: Path) -> TrackingField:
    if not isinstance(entry, dict) or not entry.get("key"):
        raise TrackingSchemaError(f"Tracking schema at {source} has a field entry missing 'key': {entry!r}")

    key = entry["key"]
    manual = bool(entry.get("manual", False))
    derived_from = entry.get("derived_from")

    if manual and derived_from:
        raise TrackingSchemaError(
            f"Tracking schema at {source}: field {key!r} cannot be both 'manual: true' and have a 'derived_from'."
        )
    if not manual and not derived_from:
        raise TrackingSchemaError(
            f"Tracking schema at {source}: field {key!r} must be 'manual: true' or declare 'derived_from'."
        )

    notion = entry.get("notion") or {}
    sqlite = entry.get("sqlite") or {}

    return TrackingField(
        key=key,
        manual=manual,
        derived_from=derived_from,
        notion_property=notion.get("property"),
        notion_type=notion.get("type"),
        sqlite_column=sqlite.get("column"),
    )
