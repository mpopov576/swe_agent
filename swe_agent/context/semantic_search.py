class SemanticSearch:
    def __init__(self, embedding_client, vector_store):
        self.embedding_client = embedding_client
        self.vector_store = vector_store

    def search(self, query: str, limit: int = 10):
        embedding = self.embedding_client.embed([query])[0]

        result = self.vector_store.search(
            embedding,
            n_results=limit,
        )

        results = []

        for chunk_id, document, metadata, distance in zip(
            result["ids"],
            result["documents"],
            result["metadatas"],
            result["distances"],
        ):
            chunk = {
                "id": chunk_id,
                "source": document,
                **metadata,
            }

            results.append({
                "chunk": chunk,
                "distance": distance,
            })

        return results