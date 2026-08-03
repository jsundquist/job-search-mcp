from job_search_mcp.vector_store.base import VectorRecord
from job_search_mcp.vector_store.in_memory_store import InMemoryVectorStore


def test_search_returns_most_similar_first():
    store = InMemoryVectorStore()
    store.upsert(
        [
            VectorRecord(id="a", vector=[1.0, 0.0], payload={"text": "a"}),
            VectorRecord(id="b", vector=[0.0, 1.0], payload={"text": "b"}),
            VectorRecord(id="c", vector=[0.9, 0.1], payload={"text": "c"}),
        ]
    )

    results = store.search(query_vector=[1.0, 0.0], top_k=2)

    assert [r.id for r in results] == ["a", "c"]


def test_search_respects_top_k():
    store = InMemoryVectorStore()
    store.upsert([VectorRecord(id=str(i), vector=[float(i), 0.0]) for i in range(5)])

    results = store.search(query_vector=[1.0, 0.0], top_k=2)

    assert len(results) == 2


def test_upsert_overwrites_existing_id():
    store = InMemoryVectorStore()
    store.upsert([VectorRecord(id="a", vector=[1.0, 0.0], payload={"v": 1})])
    store.upsert([VectorRecord(id="a", vector=[0.0, 1.0], payload={"v": 2})])

    results = store.search(query_vector=[0.0, 1.0], top_k=5)

    assert len(results) == 1
    assert results[0].payload == {"v": 2}


def test_delete_removes_record():
    store = InMemoryVectorStore()
    store.upsert([VectorRecord(id="a", vector=[1.0, 0.0])])

    store.delete(["a"])

    assert store.search(query_vector=[1.0, 0.0], top_k=5) == []
