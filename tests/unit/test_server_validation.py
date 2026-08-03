import pytest

from job_search_mcp import server


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


@pytest.mark.parametrize("job_description", ["", "   ", "\n\t"])
def test_match_job_rejects_empty_job_description(job_description):
    with pytest.raises(ValueError, match="job_description must not be empty"):
        server.match_job(job_description)


@pytest.mark.parametrize("job_id", ["", "   "])
def test_push_to_tracker_rejects_empty_job_id(job_id):
    with pytest.raises(ValueError, match="job_id must not be empty"):
        server.push_to_tracker(job_id, _verdict())
