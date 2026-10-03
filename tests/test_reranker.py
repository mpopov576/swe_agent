from swe_agent.context.reranker import ContextReranker


def test_combines_semantic_and_lexical_results():
    chunks = [
        {
            "id": "chunk_1",
            "source": "UserService authentication",
        },
        {
            "id": "chunk_2",
            "source": "Database connection",
        },
    ]

    semantic_results = [
        {
            "chunk": chunks[0],
            "distance": 0.2,
        },
        {
            "chunk": chunks[1],
            "distance": 0.4,
        },
    ]

    lexical_results = [
        {
            "chunk": chunks[0],
            "score": 3.0,
            "matched_terms": ["userservice"],
        },
    ]

    reranker = ContextReranker()

    results = reranker.rerank(
        semantic_results,
        lexical_results,
    )

    assert len(results) == 2
    assert results[0]["chunk"]["id"] == "chunk_1"


def test_deduplicates_chunks():
    chunk = {
        "id": "chunk_1",
        "source": "UserService",
    }

    semantic_results = [
        {
            "chunk": chunk,
            "distance": 0.2,
        },
    ]

    lexical_results = [
        {
            "chunk": chunk,
            "score": 2.0,
            "matched_terms": ["userservice"],
        },
    ]

    reranker = ContextReranker()

    results = reranker.rerank(
        semantic_results,
        lexical_results,
    )

    assert len(results) == 1
    assert results[0]["chunk"]["id"] == "chunk_1"


def test_limit():
    chunks = [
        {"id": "1", "source": "one"},
        {"id": "2", "source": "two"},
        {"id": "3", "source": "three"},
    ]

    semantic_results = [
        {"chunk": chunks[0], "distance": 0.1},
        {"chunk": chunks[1], "distance": 0.2},
        {"chunk": chunks[2], "distance": 0.3},
    ]

    reranker = ContextReranker()

    results = reranker.rerank(
        semantic_results,
        [],
        limit=2,
    )

    assert len(results) == 2