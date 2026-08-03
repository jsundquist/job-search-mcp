import pytest

from job_search_mcp.fit_verdict import FitVerdict
from job_search_mcp.tracking_store.mapping import (
    FIT_RATING_PROPERTY,
    KEY_NOTES_PROPERTY,
    STATUS_PROPERTY,
    STATUS_VALUE,
    build_key_notes,
    build_notion_properties,
    build_tracking_fields,
    map_bucket_to_fit_rating,
)


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


def test_build_notion_properties_shape():
    props = build_notion_properties(_verdict(bucket="Weak Fit"))

    assert props[STATUS_PROPERTY] == {"select": {"name": STATUS_VALUE}}
    assert props[FIT_RATING_PROPERTY] == {"select": {"name": "Weak Fit"}}
    assert "text" in props[KEY_NOTES_PROPERTY]["rich_text"][0]


def test_build_tracking_fields_backend_agnostic():
    fields = build_tracking_fields(_verdict(bucket="Not a Fit"))

    assert fields == {
        "status": STATUS_VALUE,
        "fit_rating": "Not a Fit",
        "notes": build_key_notes(_verdict(bucket="Not a Fit")),
    }
