import pytest
from notion_client.errors import APIErrorCode, APIResponseError

from job_search_mcp.tracking_store.notion_store import NotionTrackingStore
from job_search_mcp.tracking_store.schema import load_tracking_schema

_SCHEMA_YAML = """
fields:
  - key: status
    derived_from: status_fixed
    notion:
      property: "Status"
      type: select
  - key: fit_rating
    derived_from: fit_rating_from_bucket
    notion:
      property: "Fit Rating"
      type: select
  - key: notes
    derived_from: key_notes
    notion:
      property: "Key Notes"
      type: rich_text
  - key: company
    manual: true
    notion:
      property: "Company"
  - key: role
    manual: true
    notion:
      property: "Role"
  - key: jd_link
    manual: true
    notion:
      property: "JD Link"
"""


def _schema(tmp_path):
    schema_file = tmp_path / "tracking_schema.yaml"
    schema_file.write_text(_SCHEMA_YAML)
    return load_tracking_schema(schema_file)


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
        self.create_calls: list[dict] = []
        self._next_id = 1

    def update(self, page_id: str, properties: dict) -> None:
        if page_id in self._missing_ids:
            raise _not_found_error()
        self.update_calls.append((page_id, properties))
        self._pages[page_id]["properties"].update(properties)

    def retrieve(self, page_id: str) -> dict:
        if page_id in self._missing_ids or page_id not in self._pages:
            raise _not_found_error()
        return self._pages[page_id]

    def create(self, parent: dict, properties: dict) -> dict:
        self.create_calls.append({"parent": parent, "properties": properties})
        page_id = f"new-page-{self._next_id}"
        self._next_id += 1
        self._pages[page_id] = {"id": page_id, "archived": False, "properties": properties}
        return self._pages[page_id]


_DEFAULT_KNOWN_PROPERTIES = {
    "Status": {"type": "select"},
    "Fit Rating": {"type": "select"},
    "Key Notes": {"type": "rich_text"},
    "Company": {"type": "title"},
    "Role": {"type": "rich_text"},
    "JD Link": {"type": "url"},
}


class _FakeDatabasesEndpoint:
    def __init__(self, data_sources: list[dict] | None = None, known_properties: dict | None = None):
        self._data_sources = data_sources if data_sources is not None else [{"id": "ds-1"}]
        self._known_properties = known_properties if known_properties is not None else _DEFAULT_KNOWN_PROPERTIES

    def retrieve(self, database_id: str) -> dict:
        return {"data_sources": self._data_sources, "properties": self._known_properties}


class _FakeDataSourcesEndpoint:
    def __init__(self, pages: dict[str, dict]):
        self._pages = pages

    def query(self, data_source_id: str, start_cursor=None) -> dict:
        return {"results": list(self._pages.values()), "has_more": False, "next_cursor": None}


def _make_store(
    tmp_path,
    pages: dict[str, dict],
    missing_ids: set[str] | None = None,
    data_sources: list[dict] | None = None,
    known_properties: dict | None = None,
) -> NotionTrackingStore:
    store = NotionTrackingStore(database_id="db-1", api_key="secret", schema=_schema(tmp_path))
    store._client.pages = _FakePagesEndpoint(pages, missing_ids)
    store._client.databases = _FakeDatabasesEndpoint(data_sources, known_properties)
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


def test_record_analysis_updates_existing_page_by_id(tmp_path):
    pages = {
        "page-1": {
            "id": "page-1",
            "archived": False,
            "parent": {"type": "database_id", "database_id": "db-1"},
            "properties": {"Company": {"title": [{"plain_text": "Acme"}]}},
        }
    }
    store = _make_store(tmp_path, pages)

    store.record_analysis("page-1", _verdict(bucket="Weak Fit"))

    page_id, properties = store._client.pages.update_calls[0]
    assert page_id == "page-1"
    assert properties["Status"] == {"select": {"name": "Not yet applied"}}
    assert properties["Fit Rating"] == {"select": {"name": "Weak Fit"}}
    # untouched company property remains
    assert pages["page-1"]["properties"]["Company"] == {"title": [{"plain_text": "Acme"}]}


def test_get_analysis_parses_mapped_properties(tmp_path):
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
    store = _make_store(tmp_path, pages)

    result = store.get_analysis("page-1")

    assert result == {
        "job_id": "page-1",
        "status": "Not yet applied",
        "fit_rating": "Possible Fit",
        "notes": "Some notes",
    }


def test_get_analysis_returns_none_for_archived_page(tmp_path):
    pages = {"page-1": {"id": "page-1", "archived": True, "properties": {}}}
    store = _make_store(tmp_path, pages)

    assert store.get_analysis("page-1") is None


def test_list_analyses_returns_all_pages(tmp_path):
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
    store = _make_store(tmp_path, pages)

    results = store.list_analyses()

    assert {r["job_id"] for r in results} == {"page-1", "page-2"}


def test_record_analysis_raises_clear_error_for_unknown_job_id(tmp_path):
    store = _make_store(tmp_path, {}, missing_ids={"missing-page"})

    with pytest.raises(RuntimeError, match="No Notion page found for job_id='missing-page'"):
        store.record_analysis("missing-page", _verdict())


def test_list_analyses_raises_clear_error_when_database_has_no_data_sources(tmp_path):
    store = _make_store(tmp_path, {}, data_sources=[])

    with pytest.raises(RuntimeError, match="has no data sources"):
        store.list_analyses()


def test_record_analysis_skips_field_with_missing_notion_property_and_warns(tmp_path):
    pages = {
        "page-1": {
            "id": "page-1",
            "archived": False,
            "parent": {"type": "database_id", "database_id": "db-1"},
            "properties": {},
        }
    }
    store = _make_store(tmp_path, pages, known_properties={"Status": {}, "Fit Rating": {}})

    warnings = store.record_analysis("page-1", _verdict(bucket="Weak Fit"))

    page_id, properties = store._client.pages.update_calls[0]
    assert page_id == "page-1"
    assert "Status" in properties
    assert "Fit Rating" in properties
    assert "Key Notes" not in properties
    assert any("Key Notes" in warning for warning in warnings)


def test_record_analysis_returns_no_warnings_when_schema_matches_database(tmp_path):
    pages = {
        "page-1": {
            "id": "page-1",
            "archived": False,
            "parent": {"type": "database_id", "database_id": "db-1"},
            "properties": {},
        }
    }
    store = _make_store(tmp_path, pages)

    warnings = store.record_analysis("page-1", _verdict())

    assert warnings == []


def test_record_analysis_refuses_to_write_page_outside_configured_database(tmp_path):
    pages = {
        "page-1": {
            "id": "page-1",
            "archived": False,
            "parent": {"type": "database_id", "database_id": "some-other-db"},
            "properties": {},
        }
    }
    store = _make_store(tmp_path, pages)

    with pytest.raises(RuntimeError, match="does not belong to the configured tracking database"):
        store.record_analysis("page-1", _verdict())
    assert store._client.pages.update_calls == []


def test_find_by_company_role_returns_matching_job_id_case_insensitive(tmp_path):
    pages = {
        "page-1": {
            "id": "page-1",
            "archived": False,
            "properties": {
                "Company": {"title": [{"plain_text": "Acme"}]},
                "Role": {"rich_text": [{"plain_text": "Staff Engineer"}]},
            },
        }
    }
    store = _make_store(tmp_path, pages)

    assert store.find_by_company_role("acme", "STAFF ENGINEER") == "page-1"
    assert store.find_by_company_role("Acme", "Principal Engineer") is None


def test_find_by_company_role_skips_archived_pages(tmp_path):
    pages = {
        "page-1": {
            "id": "page-1",
            "archived": True,
            "properties": {
                "Company": {"title": [{"plain_text": "Acme"}]},
                "Role": {"rich_text": [{"plain_text": "Staff Engineer"}]},
            },
        }
    }
    store = _make_store(tmp_path, pages)

    assert store.find_by_company_role("Acme", "Staff Engineer") is None


def test_find_by_company_role_requires_company_and_role_fields(tmp_path):
    schema_file = tmp_path / "tracking_schema.yaml"
    schema_file.write_text(
        "fields:\n  - key: status\n    derived_from: status_fixed\n    notion:\n      "
        "property: Status\n      type: select\n"
    )
    store = NotionTrackingStore(database_id="db-1", api_key="secret", schema=load_tracking_schema(schema_file))

    with pytest.raises(RuntimeError, match="requires 'company' and 'role' fields"):
        store.find_by_company_role("Acme", "Staff Engineer")


def test_create_application_writes_title_rich_text_and_url(tmp_path):
    pages: dict[str, dict] = {}
    store = _make_store(tmp_path, pages)

    job_id = store.create_application("Acme", "Staff Engineer", source_url="https://example.com/job")

    assert job_id in pages
    create_call = store._client.pages.create_calls[0]
    properties = create_call["properties"]
    assert properties["Company"] == {"title": [{"text": {"content": "Acme"}}]}
    assert properties["Role"] == {"rich_text": [{"text": {"content": "Staff Engineer"}}]}
    assert properties["JD Link"] == {"url": "https://example.com/job"}
    assert create_call["parent"] == {"database_id": "db-1"}


def test_create_application_without_source_url_omits_jd_link(tmp_path):
    pages: dict[str, dict] = {}
    store = _make_store(tmp_path, pages)

    store.create_application("Acme", "Staff Engineer")

    properties = store._client.pages.create_calls[0]["properties"]
    assert "JD Link" not in properties


def test_update_status_writes_only_status_property(tmp_path):
    pages = {
        "page-1": {
            "id": "page-1",
            "archived": False,
            "parent": {"type": "database_id", "database_id": "db-1"},
            "properties": {},
        }
    }
    store = _make_store(tmp_path, pages)

    store.update_status("page-1", "Applied")

    page_id, properties = store._client.pages.update_calls[0]
    assert page_id == "page-1"
    assert properties == {"Status": {"select": {"name": "Applied"}}}


def test_update_status_raises_clear_error_for_unknown_job_id(tmp_path):
    store = _make_store(tmp_path, {}, missing_ids={"missing-page"})

    with pytest.raises(RuntimeError, match="No Notion page found for job_id='missing-page'"):
        store.update_status("missing-page", "Applied")


def test_update_status_refuses_to_write_page_outside_configured_database(tmp_path):
    pages = {
        "page-1": {
            "id": "page-1",
            "archived": False,
            "parent": {"type": "database_id", "database_id": "some-other-db"},
            "properties": {},
        }
    }
    store = _make_store(tmp_path, pages)

    with pytest.raises(RuntimeError, match="does not belong to the configured tracking database"):
        store.update_status("page-1", "Applied")
    assert store._client.pages.update_calls == []


def test_update_status_refuses_unrecognized_select_option(tmp_path):
    pages = {
        "page-1": {
            "id": "page-1",
            "archived": False,
            "parent": {"type": "database_id", "database_id": "db-1"},
            "properties": {},
        }
    }
    known_properties = dict(_DEFAULT_KNOWN_PROPERTIES)
    known_properties["Status"] = {
        "type": "select",
        "select": {"options": [{"name": "Applied"}, {"name": "Rejected"}]},
    }
    store = _make_store(tmp_path, pages, known_properties=known_properties)

    with pytest.raises(RuntimeError, match="not one of the configured Status options"):
        store.update_status("page-1", "Ghosted")
    assert store._client.pages.update_calls == []


def test_update_status_accepts_a_configured_select_option(tmp_path):
    pages = {
        "page-1": {
            "id": "page-1",
            "archived": False,
            "parent": {"type": "database_id", "database_id": "db-1"},
            "properties": {},
        }
    }
    known_properties = dict(_DEFAULT_KNOWN_PROPERTIES)
    known_properties["Status"] = {
        "type": "select",
        "select": {"options": [{"name": "Applied"}, {"name": "Rejected"}]},
    }
    store = _make_store(tmp_path, pages, known_properties=known_properties)

    store.update_status("page-1", "Rejected")

    page_id, properties = store._client.pages.update_calls[0]
    assert page_id == "page-1"
    assert properties == {"Status": {"select": {"name": "Rejected"}}}
