from pathlib import Path

import chromadb


class VectorChromaStore:
    def __init__(
        self,
        storage_path: str | Path | None,
        collection_name: str,
    ):
        if storage_path is None:
            self._client = chromadb.EphemeralClient()

        else:
            Path(storage_path).mkdir(
                parents=True,
                exist_ok=True,
            )

            self._client = chromadb.PersistentClient(
                path=str(storage_path),
            )

        self._collection = (
            self._client.get_or_create_collection(
                name=collection_name,
            )
        )

    def add(
        self,
        ids: list[str],
        embeddings: list[list[float]],
        documents: list[str],
        metadatas: list[dict],
    ):
        if not (
            len(ids)
            == len(embeddings)
            == len(documents)
            == len(metadatas)
        ):
            raise ValueError(
                "All inputs must have the same length"
            )

        self._collection.upsert(
            ids=ids,
            embeddings=embeddings,
            documents=documents,
            metadatas=metadatas,
        )

    def search(
        self,
        embedding: list[float],
        n_results: int = 10,
        where: dict | None = None,
    ):
        result = self._collection.query(
            query_embeddings=[embedding],
            n_results=n_results,
            where=where,
        )

        return {
            "ids": result["ids"][0],
            "documents": result["documents"][0],
            "metadatas": result["metadatas"][0],
            "distances": result["distances"][0],
        }

    def delete(self, ids: list[str]):
        self._collection.delete(ids=ids)

    def count(self):
        return self._collection.count()