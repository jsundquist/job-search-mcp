import pytest

from job_search_mcp.tracking_store.schema import (
    TrackingSchemaError,
    load_tracking_schema,
)

VALID_SCHEMA = """
fields:
  - key: status
    derived_from: status_fixed
    notion:
      property: "Status"
      type: select
    sqlite:
      column: status
  - key: company
    manual: true
    notion:
      property: "Company"
"""


def test_loads_valid_schema(tmp_path):
    schema_file = tmp_path / "tracking_schema.yaml"
    schema_file.write_text(VALID_SCHEMA)

    schema = load_tracking_schema(schema_file)

    assert [f.key for f in schema.fields] == ["status", "company"]


def test_tool_populated_fields_excludes_manual_fields(tmp_path):
    schema_file = tmp_path / "tracking_schema.yaml"
    schema_file.write_text(VALID_SCHEMA)

    schema = load_tracking_schema(schema_file)

    assert [f.key for f in schema.tool_populated_fields()] == ["status"]


def test_parses_notion_and_sqlite_locations(tmp_path):
    schema_file = tmp_path / "tracking_schema.yaml"
    schema_file.write_text(VALID_SCHEMA)

    schema = load_tracking_schema(schema_file)
    status_field = schema.fields[0]

    assert status_field.derived_from == "status_fixed"
    assert status_field.notion_property == "Status"
    assert status_field.notion_type == "select"
    assert status_field.sqlite_column == "status"


def test_missing_file_raises_schema_error(tmp_path):
    with pytest.raises(TrackingSchemaError, match="Could not read tracking schema"):
        load_tracking_schema(tmp_path / "does_not_exist.yaml")


def test_invalid_yaml_raises_schema_error(tmp_path):
    schema_file = tmp_path / "tracking_schema.yaml"
    schema_file.write_text("fields: [this: is not: valid yaml")

    with pytest.raises(TrackingSchemaError, match="not valid YAML"):
        load_tracking_schema(schema_file)


def test_missing_fields_key_raises_schema_error(tmp_path):
    schema_file = tmp_path / "tracking_schema.yaml"
    schema_file.write_text("not_fields: []")

    with pytest.raises(TrackingSchemaError, match="top-level 'fields' list"):
        load_tracking_schema(schema_file)


def test_empty_fields_list_raises_schema_error(tmp_path):
    schema_file = tmp_path / "tracking_schema.yaml"
    schema_file.write_text("fields: []")

    with pytest.raises(TrackingSchemaError, match="at least one entry"):
        load_tracking_schema(schema_file)


def test_field_missing_key_raises_schema_error(tmp_path):
    schema_file = tmp_path / "tracking_schema.yaml"
    schema_file.write_text("fields:\n  - manual: true\n")

    with pytest.raises(TrackingSchemaError, match="missing 'key'"):
        load_tracking_schema(schema_file)


def test_duplicate_key_raises_schema_error(tmp_path):
    schema_file = tmp_path / "tracking_schema.yaml"
    schema_file.write_text(
        "fields:\n"
        "  - key: status\n"
        "    manual: true\n"
        "  - key: status\n"
        "    manual: true\n"
    )

    with pytest.raises(TrackingSchemaError, match="more than once"):
        load_tracking_schema(schema_file)


def test_field_neither_manual_nor_derived_raises_schema_error(tmp_path):
    schema_file = tmp_path / "tracking_schema.yaml"
    schema_file.write_text("fields:\n  - key: status\n")

    with pytest.raises(TrackingSchemaError, match="must be 'manual: true' or declare 'derived_from'"):
        load_tracking_schema(schema_file)


def test_field_both_manual_and_derived_raises_schema_error(tmp_path):
    schema_file = tmp_path / "tracking_schema.yaml"
    schema_file.write_text("fields:\n  - key: status\n    manual: true\n    derived_from: status_fixed\n")

    with pytest.raises(TrackingSchemaError, match="cannot be both"):
        load_tracking_schema(schema_file)
