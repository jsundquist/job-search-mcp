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


class _FakeTrackingStore:
    def __init__(self):
        self.recorded: list[tuple[str, dict]] = []

    def record_analysis(self, job_id, analysis):
        self.recorded.append((job_id, analysis))

    def get_analysis(self, job_id):
        raise NotImplementedError

    def list_analyses(self):
        raise NotImplementedError


def test_push_to_tracker_dry_run_does_not_write(monkeypatch):
    fake_store = _FakeTrackingStore()
    monkeypatch.setattr(server, "_get_tracking_store", lambda: fake_store)

    result = server.push_to_tracker("page-1", _verdict(bucket="Possible Fit"), dry_run=True)

    assert result["dry_run"] is True
    assert result["job_id"] == "page-1"
    assert result["properties"]["Status"] == {"select": {"name": "Not yet applied"}}
    assert result["properties"]["Fit rating"] == {"select": {"name": "Possible Fit"}}
    assert fake_store.recorded == []


def test_push_to_tracker_writes_when_not_dry_run(monkeypatch):
    fake_store = _FakeTrackingStore()
    monkeypatch.setattr(server, "_get_tracking_store", lambda: fake_store)

    result = server.push_to_tracker("page-1", _verdict(bucket="Not a Fit"))

    assert result["dry_run"] is False
    assert fake_store.recorded == [("page-1", _verdict(bucket="Not a Fit"))]
