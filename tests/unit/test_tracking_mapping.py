import pytest

from job_search_mcp.fit_verdict import FitVerdict
from job_search_mcp.tracking_store.mapping import (
    STATUS_VALUE,
    build_key_notes,
    build_notion_properties_from_schema,
    build_sqlite_fields_from_schema,
    compute_derived_value,
    map_bucket_to_fit_rating,
    notion_property_payload,
    parse_notion_property,
)
from job_search_mcp.tracking_store.schema import load_tracking_schema

_SCHEMA_YAML = """
fields:
  - key: status
    derived_from: status_fixed
    notion:
      property: "Status"
      type: select
    sqlite:
      column: status
  - key: fit_rating
    derived_from: fit_rating_from_bucket
    notion:
      property: "Fit Rating"
      type: select
    sqlite:
      column: fit_rating
  - key: notes
    derived_from: key_notes
    notion:
      property: "Key Notes"
      type: rich_text
    sqlite:
      column: notes
  - key: company
    manual: true
    notion:
      property: "Company"
"""


def _verdict(**overrides) -> FitVerdict:
    base: FitVerdict = {
        "gate_failures": [],
        "domain_match": {"category": "high", "rationale": "same domain"},
        "scope_match": {"category": "high", "rationale": "same scope"},
        "preference_severity": {"category": "no penalty", "rationale": "remote"},
        "red_flags": [],
        "rationale": "Strong overall match.",
        "demotion_count": 0,
        "bucket": "Strong Fit",
    }
    base.update(overrides)
    return base


def _schema(tmp_path):
    schema_file = tmp_path / "tracking_schema.yaml"
    schema_file.write_text(_SCHEMA_YAML)
    return load_tracking_schema(schema_file)


@pytest.mark.parametrize(
    "bucket,expected",
    [
        ("Strong Fit", "Strong Fit"),
        ("Good Fit", "Good Fit"),
        ("Possible Fit", "Possible Fit"),
        ("Weak Fit", "Weak Fit"),
        ("Not a Fit", "Not a Fit"),
    ],
)
def test_map_bucket_to_fit_rating(bucket, expected):
    assert map_bucket_to_fit_rating(bucket) == expected


def test_map_bucket_to_fit_rating_rejects_unknown_bucket():
    with pytest.raises(ValueError):
        map_bucket_to_fit_rating("Excellent Fit")


def test_build_key_notes_includes_rationale_and_itemized_lists():
    verdict = _verdict(
        gate_failures=["Go required, not in resume"],
        red_flags=["Unclear reporting line"],
        rationale="Overall summary.",
    )

    notes = build_key_notes(verdict)

    assert "Overall summary." in notes
    assert "- Go required, not in resume" in notes
    assert "- Unclear reporting line" in notes
    assert "Domain match (high): same domain" in notes


def test_build_key_notes_omits_empty_sections():
    notes = build_key_notes(_verdict())

    assert "Gate failures:" not in notes
    assert "Red flags:" not in notes


def test_compute_derived_value_dispatches_known_sources():
    verdict = _verdict(bucket="Weak Fit")

    assert compute_derived_value("status_fixed", verdict) == STATUS_VALUE
    assert compute_derived_value("fit_rating_from_bucket", verdict) == "Weak Fit"
    assert compute_derived_value("key_notes", verdict) == build_key_notes(verdict)


def test_compute_derived_value_rejects_unknown_source():
    with pytest.raises(ValueError, match="Unrecognized derived_from"):
        compute_derived_value("not_a_real_source", _verdict())


def test_build_notion_properties_from_schema_only_includes_tool_populated_fields(tmp_path):
    schema = _schema(tmp_path)

    props, warnings = build_notion_properties_from_schema(schema, _verdict(bucket="Weak Fit"))

    assert props["Status"] == {"select": {"name": STATUS_VALUE}}
    assert props["Fit Rating"] == {"select": {"name": "Weak Fit"}}
    assert "text" in props["Key Notes"]["rich_text"][0]
    assert "Company" not in props
    assert warnings == []


def test_build_notion_properties_from_schema_warns_and_skips_missing_known_property(tmp_path):
    schema = _schema(tmp_path)

    props, warnings = build_notion_properties_from_schema(
        schema, _verdict(), known_properties={"Status": {}, "Fit Rating": {}}
    )

    assert "Status" in props
    assert "Fit Rating" in props
    assert "Key Notes" not in props
    assert len(warnings) == 1
    assert "Key Notes" in warnings[0]


def test_build_sqlite_fields_from_schema(tmp_path):
    schema = _schema(tmp_path)
    verdict = _verdict(bucket="Not a Fit")

    fields, warnings = build_sqlite_fields_from_schema(schema, verdict)

    assert fields == {
        "status": STATUS_VALUE,
        "fit_rating": "Not a Fit",
        "notes": build_key_notes(verdict),
    }
    assert warnings == []


def test_build_notion_properties_from_schema_warns_and_skips_unrecognized_derived_from(tmp_path):
    schema_file = tmp_path / "tracking_schema.yaml"
    schema_file.write_text(
        "fields:\n"
        "  - key: status\n"
        "    derived_from: status_fixed\n"
        "    notion:\n"
        "      property: Status\n"
        "      type: select\n"
        "  - key: mystery\n"
        "    derived_from: not_a_real_source\n"
        "    notion:\n"
        "      property: Mystery\n"
        "      type: select\n"
    )
    schema = load_tracking_schema(schema_file)

    props, warnings = build_notion_properties_from_schema(schema, _verdict())

    assert "Status" in props
    assert "Mystery" not in props
    assert len(warnings) == 1
    assert "mystery" in warnings[0]
    assert "not_a_real_source" in warnings[0]


def test_parse_notion_property_select():
    assert parse_notion_property({"select": {"name": "Strong Fit"}}, "select") == "Strong Fit"
    assert parse_notion_property({}, "select") is None


def test_parse_notion_property_rich_text():
    prop = {"rich_text": [{"plain_text": "hello "}, {"plain_text": "world"}]}
    assert parse_notion_property(prop, "rich_text") == "hello world"
    assert parse_notion_property({}, "rich_text") == ""


def test_notion_property_payload_and_parse_title_round_trip():
    payload = notion_property_payload("title", "Acme — Staff Engineer")
    assert payload == {"title": [{"text": {"content": "Acme — Staff Engineer"}}]}

    prop = {"title": [{"plain_text": "Acme — "}, {"plain_text": "Staff Engineer"}]}
    assert parse_notion_property(prop, "title") == "Acme — Staff Engineer"
    assert parse_notion_property({}, "title") == ""


def test_notion_property_payload_and_parse_url_round_trip():
    payload = notion_property_payload("url", "https://example.com/job")
    assert payload == {"url": "https://example.com/job"}
    assert parse_notion_property({"url": "https://example.com/job"}, "url") == "https://example.com/job"
    assert parse_notion_property({}, "url") is None
