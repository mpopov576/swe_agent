from swe_agent.context.lexical_search import LexicalSearch


def test_finds_matching_chunk():
    chunks = [
        {
            "id": "chunk_1",
            "name": "UserService",
            "source": (
                "class UserService:\n"
                "    def create_user(self):\n"
                "        pass"
            ),
        },
        {
            "id": "chunk_2",
            "name": "Database",
            "source": (
                "class Database:\n"
                "    def connect(self):\n"
                "        pass"
            ),
        },
    ]

    search = LexicalSearch(chunks)

    results = search.search("UserService")

    assert len(results) == 1
    assert results[0]["chunk"]["id"] == "chunk_1"


def test_returns_matching_terms():
    chunks = [
        {
            "id": "chunk_1",
            "name": "UserService",
            "source": (
                "class UserService:\n"
                "    def create_user(self):\n"
                "        pass"
            ),
        },
    ]

    search = LexicalSearch(chunks)

    results = search.search(
        "UserService create_user"
    )

    assert len(results) == 1

    assert "userservice" in results[0]["matched_terms"]
    assert "create_user" in results[0]["matched_terms"]


def test_results_are_sorted_by_score():
    chunks = [
        {
            "id": "chunk_1",
            "source": "database connection",
        },
        {
            "id": "chunk_2",
            "source": (
                "database connection\n"
                "database query\n"
                "database"
            ),
        },
    ]

    search = LexicalSearch(chunks)

    results = search.search("database")

    assert results[0]["chunk"]["id"] == "chunk_2"


def test_no_match():
    chunks = [
        {
            "id": "chunk_1",
            "source": "authentication service",
        },
    ]

    search = LexicalSearch(chunks)

    results = search.search("database")

    assert results == []
