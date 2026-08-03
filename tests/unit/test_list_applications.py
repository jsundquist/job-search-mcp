from job_search_mcp import server


class _FakeTrackingStore:
    def __init__(self, analyses: list[dict]):
        self._analyses = analyses

    def record_analysis(self, job_id, analysis):
        raise NotImplementedError

    def get_analysis(self, job_id):
        raise NotImplementedError

    def list_analyses(self):
        return self._analyses


def test_list_applications_returns_all_when_no_status_given(monkeypatch):
    analyses = [
        {"job_id": "page-1", "status": "Not yet applied", "fit_rating": "Strong Fit", "notes": ""},
        {"job_id": "page-2", "status": "Applied", "fit_rating": "Good Fit", "notes": ""},
    ]
    monkeypatch.setattr(server, "_get_tracking_store", lambda: _FakeTrackingStore(analyses))

    result = server.list_applications()

    assert result == analyses


def test_list_applications_filters_by_status(monkeypatch):
    analyses = [
        {"job_id": "page-1", "status": "Not yet applied", "fit_rating": "Strong Fit", "notes": ""},
        {"job_id": "page-2", "status": "Applied", "fit_rating": "Good Fit", "notes": ""},
        {"job_id": "page-3", "status": "Applied", "fit_rating": "Weak Fit", "notes": ""},
    ]
    monkeypatch.setattr(server, "_get_tracking_store", lambda: _FakeTrackingStore(analyses))

    result = server.list_applications(status="Applied")

    assert {r["job_id"] for r in result} == {"page-2", "page-3"}


def test_list_applications_returns_empty_list_for_no_matches(monkeypatch):
    analyses = [{"job_id": "page-1", "status": "Not yet applied", "fit_rating": "Strong Fit", "notes": ""}]
    monkeypatch.setattr(server, "_get_tracking_store", lambda: _FakeTrackingStore(analyses))

    result = server.list_applications(status="Rejected")

    assert result == []
