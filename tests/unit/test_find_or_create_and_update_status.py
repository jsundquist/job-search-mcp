import pytest

from job_search_mcp import server


class _FakeTrackingStore:
    def __init__(self, existing_job_id: str | None = None):
        self._existing_job_id = existing_job_id
        self.find_calls: list[tuple[str, str]] = []
        self.create_calls: list[tuple[str, str, str | None]] = []
        self.update_status_calls: list[tuple[str, str]] = []

    def record_analysis(self, job_id, analysis):
        raise NotImplementedError

    def get_analysis(self, job_id):
        raise NotImplementedError

    def list_analyses(self):
        raise NotImplementedError

    def find_by_company_role(self, company, role):
        self.find_calls.append((company, role))
        return self._existing_job_id

    def create_application(self, company, role, source_url=None):
        self.create_calls.append((company, role, source_url))
        return "new-page-1"

    def update_status(self, job_id, status):
        self.update_status_calls.append((job_id, status))


def test_find_or_create_application_returns_existing_match(monkeypatch):
    fake_store = _FakeTrackingStore(existing_job_id="page-1")
    monkeypatch.setattr(server, "_get_tracking_store", lambda: fake_store)

    result = server.find_or_create_application("Acme", "Staff Engineer")

    assert result == {"job_id": "page-1", "created": False}
    assert fake_store.create_calls == []


def test_find_or_create_application_creates_when_no_match(monkeypatch):
    fake_store = _FakeTrackingStore(existing_job_id=None)
    monkeypatch.setattr(server, "_get_tracking_store", lambda: fake_store)

    result = server.find_or_create_application("Acme", "Staff Engineer", source_url="https://example.com/job")

    assert result == {"job_id": "new-page-1", "created": True}
    assert fake_store.create_calls == [("Acme", "Staff Engineer", "https://example.com/job")]


def test_find_or_create_application_dry_run_never_creates(monkeypatch):
    fake_store = _FakeTrackingStore(existing_job_id=None)
    monkeypatch.setattr(server, "_get_tracking_store", lambda: fake_store)

    result = server.find_or_create_application("Acme", "Staff Engineer", dry_run=True)

    assert result == {"job_id": None, "created": False}
    assert fake_store.create_calls == []


@pytest.mark.parametrize("company", ["", "   "])
def test_find_or_create_application_rejects_empty_company(company):
    with pytest.raises(ValueError, match="company must not be empty"):
        server.find_or_create_application(company, "Staff Engineer")


@pytest.mark.parametrize("role", ["", "   "])
def test_find_or_create_application_rejects_empty_role(role):
    with pytest.raises(ValueError, match="role must not be empty"):
        server.find_or_create_application("Acme", role)


def test_update_status_writes_through_to_store(monkeypatch):
    fake_store = _FakeTrackingStore()
    monkeypatch.setattr(server, "_get_tracking_store", lambda: fake_store)

    result = server.update_status("page-1", "Applied")

    assert result == {"job_id": "page-1", "status": "Applied", "dry_run": False}
    assert fake_store.update_status_calls == [("page-1", "Applied")]


def test_update_status_dry_run_does_not_write(monkeypatch):
    fake_store = _FakeTrackingStore()
    monkeypatch.setattr(server, "_get_tracking_store", lambda: fake_store)

    result = server.update_status("page-1", "Applied", dry_run=True)

    assert result == {"job_id": "page-1", "status": "Applied", "dry_run": True}
    assert fake_store.update_status_calls == []


@pytest.mark.parametrize("job_id", ["", "   "])
def test_update_status_rejects_empty_job_id(job_id):
    with pytest.raises(ValueError, match="job_id must not be empty"):
        server.update_status(job_id, "Applied")


@pytest.mark.parametrize("status", ["", "   "])
def test_update_status_rejects_empty_status(status):
    with pytest.raises(ValueError, match="status must not be empty"):
        server.update_status("page-1", status)
