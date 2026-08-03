import pytest

from job_search_mcp.tracking_store.mapping import build_key_notes
from job_search_mcp.tracking_store.schema import load_tracking_schema
from job_search_mcp.tracking_store.sqlite_store import SQLiteTrackingStore

_SCHEMA_YAML = """
fields:
  - key: status
    derived_from: status_fixed
    sqlite:
      column: status
  - key: fit_rating
    derived_from: fit_rating_from_bucket
    sqlite:
      column: fit_rating
  - key: notes
    derived_from: key_notes
    sqlite:
      column: notes
  - key: company
    manual: true
"""


def _verdict(**overrides):
    base = {
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


@pytest.fixture
def schema(tmp_path):
    schema_file = tmp_path / "tracking_schema.yaml"
    schema_file.write_text(_SCHEMA_YAML)
    return load_tracking_schema(schema_file)


@pytest.fixture
def store(schema):
    s = SQLiteTrackingStore(":memory:", schema)
    yield s
    s.close()


def test_record_and_get_analysis_round_trips(store):
    verdict = _verdict(bucket="Weak Fit")
    store.record_analysis("job-1", verdict)

    result = store.get_analysis("job-1")

    assert result == {
        "job_id": "job-1",
        "status": "Not yet applied",
        "fit_rating": "Weak Fit",
        "notes": build_key_notes(verdict),
    }


def test_get_analysis_returns_none_when_missing(store):
    assert store.get_analysis("missing") is None


def test_record_analysis_upserts_existing_job(store):
    store.record_analysis("job-1", _verdict(bucket="Strong Fit"))
    store.record_analysis("job-1", _verdict(bucket="Not a Fit"))

    result = store.get_analysis("job-1")

    assert result["fit_rating"] == "Not a Fit"
    assert len(store.list_analyses()) == 1


def test_list_analyses_returns_all_recorded_jobs(store):
    store.record_analysis("job-1", _verdict(bucket="Strong Fit"))
    store.record_analysis("job-2", _verdict(bucket="Good Fit"))

    results = store.list_analyses()

    assert {r["job_id"] for r in results} == {"job-1", "job-2"}


def test_record_analysis_returns_no_warnings_for_a_valid_schema(store):
    assert store.record_analysis("job-1", _verdict()) == []


def test_record_analysis_warns_and_skips_unrecognized_derived_from(tmp_path):
    schema_file = tmp_path / "tracking_schema.yaml"
    schema_file.write_text(
        "fields:\n"
        "  - key: status\n"
        "    derived_from: status_fixed\n"
        "    sqlite:\n"
        "      column: status\n"
        "  - key: mystery\n"
        "    derived_from: not_a_real_source\n"
        "    sqlite:\n"
        "      column: mystery\n"
    )
    schema = load_tracking_schema(schema_file)
    store = SQLiteTrackingStore(":memory:", schema)
    try:
        warnings = store.record_analysis("job-1", _verdict())

        assert len(warnings) == 1
        assert "mystery" in warnings[0]
        result = store.get_analysis("job-1")
        assert result["status"] == "Not yet applied"
        assert result["mystery"] is None
    finally:
        store.close()
