class ContextManager:
    def __init__(
        self,
        semantic_search,
        lexical_search,
        reranker,
        dependency_graph,
        assembler,
    ):
        self.semantic_search = semantic_search
        self.lexical_search = lexical_search
        self.reranker = reranker
        self.dependency_graph = dependency_graph
        self.assembler = assembler

    def retrieve(self, query: str, limit: int = 10):
        semantic_results = self.semantic_search.search(
            query,
            limit=limit,
        )

        lexical_results = self.lexical_search.search(
            query,
            limit=limit,
        )

        reranked_results = self.reranker.rerank(
            semantic_results,
            lexical_results,
            limit=limit,
        )

        return self.assembler.assemble(
            reranked_results,
            dependency_depth=1,
        )


class RepositoryContext:
    def __init__(
        self,
        repo_path,
        embedding_model,
        deadline,
    ):
        self.repo_path = str(repo_path)
        self.embedding_model = embedding_model
        self.deadline = deadline

    def retrieve(self, query):
        from swe_agent.limits import isolated_call

        # Each call rebuilds retrieval from the current files.
        # The worker can be terminated if retrieval hangs.
        return isolated_call(
            _retrieve_current_repository,
            (
                self.repo_path,
                self.embedding_model,
                query,
            ),
            180,
            self.deadline,
            "retrieval_timeout",
        )


def _retrieve_current_repository(
    repo_path,
    embedding_model,
    query,
):
    # Load expensive dependencies inside the bounded worker.
    from swe_agent.limits import CONTEXT_LIMIT, clip
    from swe_agent.context.index import build_index
    from swe_agent.context.embeddings.manager import (
        EmbeddingModelManager,
    )
    from swe_agent.context.embeddings.client import (
        EmbeddingClient,
    )
    from swe_agent.context.vector_store.chroma import (
        VectorChromaStore,
    )
    from swe_agent.context.semantic_search import (
        SemanticSearch,
    )
    from swe_agent.context.lexical_search import (
        LexicalSearch,
    )
    from swe_agent.context.reranker import ContextReranker
    from swe_agent.context.dependency_graph import (
        DependencyGraph,
    )
    from swe_agent.context.assembler import ContextAssembler
    from swe_agent.context.call_detection import (
        populate_dependency_graph,
    )

    chunks = build_index(repo_path)

    if not chunks:
        return (
            "No indexed code. Inspect repository files "
            "with the tools."
        )

    if (
        len(chunks) > 10_000
        or sum(
            len(chunk["source"])
            for chunk in chunks
        ) > 20_000_000
    ):
        raise ValueError(
            "Repository exceeds the indexing budget"
        )

    manager = EmbeddingModelManager(embedding_model)
    client = EmbeddingClient(manager)

    manager.start_session()

    try:
        client.load()

        # A new process and in-memory store ensure that
        # deleted or renamed chunks cannot survive a retry.
        store = VectorChromaStore(
            storage_path=None,
            collection_name="repo_chunks",
        )

        for offset in range(0, len(chunks), 64):
            batch = chunks[offset:offset + 64]

            store.add(
                ids=[
                    chunk["id"]
                    for chunk in batch
                ],
                embeddings=client.embed([
                    chunk["source"]
                    for chunk in batch
                ]),
                documents=[
                    chunk["source"]
                    for chunk in batch
                ],
                metadatas=[
                    {
                        key: value
                        for key, value in chunk.items()
                        if key not in ("id", "source")
                    }
                    for chunk in batch
                ],
            )

        dependency_graph = DependencyGraph()

        populate_dependency_graph(
            chunks,
            dependency_graph,
        )

        context_manager = ContextManager(
            semantic_search=SemanticSearch(
                client,
                store,
            ),
            lexical_search=LexicalSearch(chunks),
            reranker=ContextReranker(),
            dependency_graph=dependency_graph,
            assembler=ContextAssembler(
                dependency_graph=dependency_graph,
                chunks_by_id={
                    chunk["id"]: chunk
                    for chunk in chunks
                },
            ),
        )

        return clip(
            context_manager.retrieve(
                query,
                limit=min(10, len(chunks)),
            ),
            CONTEXT_LIMIT,
        )

    finally:
        client.unload()
        manager.stop_session()