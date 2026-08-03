from job_search_mcp import server
from job_search_mcp.tracking_store.schema import TrackingField, TrackingSchema


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


def _fake_schema() -> TrackingSchema:
    return TrackingSchema(
        fields=[
            TrackingField(
                key="status", manual=False, derived_from="status_fixed", notion_property="Status", notion_type="select"
            ),
            TrackingField(
                key="fit_rating",
                manual=False,
                derived_from="fit_rating_from_bucket",
                notion_property="Fit Rating",
                notion_type="select",
            ),
            TrackingField(
                key="notes",
                manual=False,
                derived_from="key_notes",
                notion_property="Key Notes",
                notion_type="rich_text",
            ),
        ]
    )


class _FakeTrackingStore:
    def __init__(self):
        self.recorded: list[tuple[str, dict]] = []

    def record_analysis(self, job_id, analysis) -> list[str]:
        self.recorded.append((job_id, analysis))
        return []

    def get_analysis(self, job_id):
        raise NotImplementedError

    def list_analyses(self):
        raise NotImplementedError


def test_push_to_tracker_dry_run_does_not_write(monkeypatch):
    fake_store = _FakeTrackingStore()
    monkeypatch.setattr(server, "_get_tracking_store", lambda: fake_store)
    monkeypatch.setattr(server, "_get_tracking_schema", _fake_schema)

    result = server.push_to_tracker("page-1", _verdict(bucket="Possible Fit"), dry_run=True)

    assert result["dry_run"] is True
    assert result["job_id"] == "page-1"
    assert result["properties"]["Status"] == {"select": {"name": "Not yet applied"}}
    assert result["properties"]["Fit Rating"] == {"select": {"name": "Possible Fit"}}
    assert result["warnings"] == []
    assert fake_store.recorded == []


def test_push_to_tracker_writes_when_not_dry_run(monkeypatch):
    fake_store = _FakeTrackingStore()
    monkeypatch.setattr(server, "_get_tracking_store", lambda: fake_store)
    monkeypatch.setattr(server, "_get_tracking_schema", _fake_schema)

    result = server.push_to_tracker("page-1", _verdict(bucket="Not a Fit"))

    assert result["dry_run"] is False
    assert result["warnings"] == []
    assert fake_store.recorded == [("page-1", _verdict(bucket="Not a Fit"))]
