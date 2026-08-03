from pathlib import Path

from job_search_mcp.ingest import ingest_resume
from job_search_mcp.resume_source.file_source import FileResumeSource
from job_search_mcp.vector_store.in_memory_store import InMemoryVectorStore
from tests.fakes import FakeEmbedder

FIXTURES = Path(__file__).parent.parent / "fixtures" / "resumes"


def test_ingest_resume_upserts_one_record_per_chunk():
    source = FileResumeSource(FIXTURES / "sample_resume.txt")
    embedder = FakeEmbedder()
    store = InMemoryVectorStore()

    ingest_resume(source, embedder, store, doc_id="resume")

    results = store.search(query_vector=embedder.embed("anything"), top_k=10)
    assert len(results) == 3
    assert all(r.id.startswith("resume::chunk-") for r in results)
    assert all(r.payload["resume_id"] == "resume" for r in results)
    assert any("Jane Example" in r.payload["text"] for r in results)
    assert any("Python" in r.payload["text"] for r in results)
