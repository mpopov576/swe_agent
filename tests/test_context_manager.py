from types import SimpleNamespace

from swe_agent.context.context_manager import ContextManager
from swe_agent.context.lexical_search import LexicalSearch
from swe_agent.context.reranker import ContextReranker
from swe_agent.context.dependency_graph import DependencyGraph
from swe_agent.context.assembler import ContextAssembler


def test_context_manager():
    chunks = [
        {
            "id": "chunk_1",
            "type": "function",
            "name": "create_user",
            "file": "users.py",
            "start_line": 1,
            "end_line": 3,
            "source": "def create_user():\n    save_user()",
        },
        {
            "id": "chunk_2",
            "type": "function",
            "name": "save_user",
            "file": "database.py",
            "start_line": 1,
            "end_line": 3,
            "source": "def save_user():\n    pass",
        },
    ]

    semantic_search = SimpleNamespace(
        search=lambda query, limit=10: [
            {
                "chunk": chunks[0],
                "distance": 0.2,
            }
        ]
    )

    lexical_search = LexicalSearch(chunks)
    reranker = ContextReranker()

    dependency_graph = DependencyGraph()

    dependency_graph.add_dependency(
        "chunk_1",
        "chunk_2",
        "calls",
    )

    assembler = ContextAssembler(
        dependency_graph=dependency_graph,
        chunks_by_id={
            chunk["id"]: chunk
            for chunk in chunks
        },
    )

    manager = ContextManager(
        semantic_search=semantic_search,
        lexical_search=lexical_search,
        reranker=reranker,
        dependency_graph=dependency_graph,
        assembler=assembler,
    )

    result = manager.retrieve(
        "create_user",
        limit=5,
    )

    assert "create_user" in result
    assert "save_user" in result
    assert "users.py" in result
    assert "database.py" in result
