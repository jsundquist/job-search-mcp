import pytest
from notion_client.errors import APIErrorCode, APIResponseError

from job_search_mcp.tracking_store.notion_store import NotionTrackingStore


def _not_found_error() -> APIResponseError:
    import httpx

    return APIResponseError(
        code=APIErrorCode.ObjectNotFound,
        status=404,
        message="Could not find page with ID: missing-page.",
        headers=httpx.Headers(),
        raw_body_text="",
    )


class _FakePagesEndpoint:
    def __init__(self, pages: dict[str, dict], missing_ids: set[str] | None = None):
        self._pages = pages
        self._missing_ids = missing_ids or set()
        self.update_calls: list[tuple[str, dict]] = []

    def update(self, page_id: str, properties: dict) -> None:
        if page_id in self._missing_ids:
            raise _not_found_error()
        self.update_calls.append((page_id, properties))
        self._pages[page_id]["properties"].update(properties)

    def retrieve(self, page_id: str) -> dict:
        return self._pages[page_id]


class _FakeDatabasesEndpoint:
    def __init__(self, data_sources: list[dict] | None = None):
        self._data_sources = data_sources if data_sources is not None else [{"id": "ds-1"}]

    def retrieve(self, database_id: str) -> dict:
        return {"data_sources": self._data_sources}


class _FakeDataSourcesEndpoint:
    def __init__(self, pages: dict[str, dict]):
        self._pages = pages

    def query(self, data_source_id: str, start_cursor=None) -> dict:
        return {"results": list(self._pages.values()), "has_more": False, "next_cursor": None}


def _make_store(
    pages: dict[str, dict], missing_ids: set[str] | None = None, data_sources: list[dict] | None = None
) -> NotionTrackingStore:
    store = NotionTrackingStore(database_id="db-1", api_key="secret")
    store._client.pages = _FakePagesEndpoint(pages, missing_ids)
    store._client.databases = _FakeDatabasesEndpoint(data_sources)
    store._client.data_sources = _FakeDataSourcesEndpoint(pages)
    return store


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


def test_record_analysis_updates_existing_page_by_id():
    pages = {
        "page-1": {
            "id": "page-1",
            "archived": False,
            "properties": {"Company": {"title": [{"plain_text": "Acme"}]}},
        }
    }
    store = _make_store(pages)

    store.record_analysis("page-1", _verdict(bucket="Weak Fit"))

    page_id, properties = store._client.pages.update_calls[0]
    assert page_id == "page-1"
    assert properties["Status"] == {"select": {"name": "Not yet applied"}}
    assert properties["Fit Rating"] == {"select": {"name": "Weak Fit"}}
    # untouched company property remains
    assert pages["page-1"]["properties"]["Company"] == {"title": [{"plain_text": "Acme"}]}


def test_get_analysis_parses_mapped_properties():
    pages = {
        "page-1": {
            "id": "page-1",
            "archived": False,
            "properties": {
                "Status": {"select": {"name": "Not yet applied"}},
                "Fit Rating": {"select": {"name": "Possible Fit"}},
                "Key Notes": {"rich_text": [{"plain_text": "Some notes"}]},
            },
        }
    }
    store = _make_store(pages)

    result = store.get_analysis("page-1")

    assert result == {
        "job_id": "page-1",
        "status": "Not yet applied",
        "fit_rating": "Possible Fit",
        "notes": "Some notes",
    }


def test_get_analysis_returns_none_for_archived_page():
    pages = {"page-1": {"id": "page-1", "archived": True, "properties": {}}}
    store = _make_store(pages)

    assert store.get_analysis("page-1") is None


def test_list_analyses_returns_all_pages():
    pages = {
        "page-1": {
            "id": "page-1",
            "archived": False,
            "properties": {
                "Status": {"select": {"name": "Not yet applied"}},
                "Fit Rating": {"select": {"name": "Strong Fit"}},
                "Key Notes": {"rich_text": []},
            },
        },
        "page-2": {
            "id": "page-2",
            "archived": False,
            "properties": {
                "Status": {"select": {"name": "Applied"}},
                "Fit Rating": {"select": {"name": "Good Fit"}},
                "Key Notes": {"rich_text": [{"plain_text": "notes"}]},
            },
        },
    }
    store = _make_store(pages)

    results = store.list_analyses()

    assert {r["job_id"] for r in results} == {"page-1", "page-2"}


def test_record_analysis_raises_clear_error_for_unknown_job_id():
    store = _make_store({}, missing_ids={"missing-page"})

    with pytest.raises(RuntimeError, match="No Notion page found for job_id='missing-page'"):
        store.record_analysis("missing-page", _verdict())


def test_list_analyses_raises_clear_error_when_database_has_no_data_sources():
    store = _make_store({}, data_sources=[])

    with pytest.raises(RuntimeError, match="has no data sources"):
        store.list_analyses()
