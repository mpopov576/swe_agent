import shutil
from pathlib import Path

from swe_agent.context.vector_store.chroma import VectorChromaStore


TEST_PATH = Path("tests") / ".chroma_test_data"


def create_store(collection_name: str):
    return VectorChromaStore(
        storage_path=TEST_PATH,
        collection_name=collection_name,
    )


def test_add_and_count():
    store = create_store("test_add_and_count")

    store.add(
        ids=["chunk_1", "chunk_2"],
        embeddings=[
            [1.0, 0.0, 0.0],
            [0.0, 1.0, 0.0],
        ],
        documents=[
            "authentication service",
            "database connection",
        ],
        metadatas=[
            {
                "repository_id": "repo_1",
                "file": "auth.py",
            },
            {
                "repository_id": "repo_1",
                "file": "database.py",
            },
        ],
    )

    assert store.count() == 2


def test_search():
    store = create_store("test_search")

    store.add(
        ids=["auth", "database", "frontend"],
        embeddings=[
            [1.0, 0.0, 0.0],
            [0.0, 1.0, 0.0],
            [0.0, 0.0, 1.0],
        ],
        documents=[
            "authentication service",
            "database connection",
            "frontend component",
        ],
        metadatas=[
            {"repository_id": "repo_1"},
            {"repository_id": "repo_1"},
            {"repository_id": "repo_1"},
        ],
    )

    result = store.search(
        embedding=[0.9, 0.1, 0.0],
        n_results=2,
    )

    assert len(result["ids"]) == 2
    assert result["ids"][0] == "auth"


def test_repository_filter():
    store = create_store("test_repository_filter")

    store.add(
        ids=["repo1_auth", "repo2_auth"],
        embeddings=[
            [1.0, 0.0],
            [1.0, 0.0],
        ],
        documents=[
            "authentication service repo 1",
            "authentication service repo 2",
        ],
        metadatas=[
            {"repository_id": "repo_1"},
            {"repository_id": "repo_2"},
        ],
    )

    result = store.search(
        embedding=[1.0, 0.0],
        n_results=10,
        where={"repository_id": "repo_1"},
    )

    assert result["ids"] == ["repo1_auth"]
    assert result["metadatas"][0]["repository_id"] == "repo_1"


def test_upsert_updates_existing_chunk():
    store = create_store("test_upsert")

    store.add(
        ids=["chunk_1"],
        embeddings=[[1.0, 0.0]],
        documents=["old content"],
        metadatas=[
            {"repository_id": "repo_1"}
        ],
    )

    store.add(
        ids=["chunk_1"],
        embeddings=[[0.0, 1.0]],
        documents=["new content"],
        metadatas=[
            {"repository_id": "repo_1"}
        ],
    )

    assert store.count() == 1

    result = store.search(
        embedding=[0.0, 1.0],
        n_results=1,
    )

    assert result["documents"][0] == "new content"


def test_delete():
    store = create_store("test_delete")

    store.add(
        ids=["chunk_1", "chunk_2"],
        embeddings=[
            [1.0, 0.0],
            [0.0, 1.0],
        ],
        documents=[
            "first",
            "second",
        ],
        metadatas=[
            {"repository_id": "repo_1"},
            {"repository_id": "repo_1"},
        ],
    )

    assert store.count() == 2

    store.delete(["chunk_1"])

    assert store.count() == 1

shutil.rmtree(TEST_PATH, ignore_errors=True)