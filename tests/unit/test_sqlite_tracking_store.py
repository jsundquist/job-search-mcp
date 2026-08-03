import pytest

from job_search_mcp.tracking_store.mapping import build_key_notes
from job_search_mcp.tracking_store.sqlite_store import SQLiteTrackingStore


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
def store():
    s = SQLiteTrackingStore(":memory:")
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

    assert result["fit_rating"] == "Not A Fit"
    assert len(store.list_analyses()) == 1


def test_list_analyses_returns_all_recorded_jobs(store):
    store.record_analysis("job-1", _verdict(bucket="Strong Fit"))
    store.record_analysis("job-2", _verdict(bucket="Good Fit"))

    results = store.list_analyses()

    assert {r["job_id"] for r in results} == {"job-1", "job-2"}
