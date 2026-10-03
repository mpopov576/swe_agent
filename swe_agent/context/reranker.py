

class ContextReranker:
    def __init__(self, semantic_weight: float = 0.7, lexical_weight: float = 0.3):
        self.semantic_weight = semantic_weight
        self.lexical_weight = lexical_weight

    def rerank(self, semantic_results: list[dict], lexical_results: list[dict], limit: int = 10):
        candidates = {}

        for result in semantic_results:
            chunk = result["chunk"]

            candidates[chunk["id"]] = {
                "chunk": chunk,
                "semantic_score": self._semantic_score(result),
                "lexical_score": 0.0,
                "matched_terms": []
            }

        for result in lexical_results:
            chunk = result["chunk"]
            chunk_id = chunk["id"]

            if chunk_id not in candidates:
                candidates[chunk_id] = {
                    "chunk": chunk,
                    "semantic_score": 0.0,
                    "lexical_score": 0.0,
                    "matched_terms": []
                }

            candidates[chunk_id]["lexical_score"] = result["score"]
            candidates[chunk_id]["matched_terms"] = (result["matched_terms"])

        max_lexical_score = max(
            (
                candidate["lexical_score"]
                for candidate in candidates.values()
            ),
            default=1.0
        )

        for candidate in candidates.values():
            lexical_score = candidate["lexical_score"]

            if max_lexical_score > 0:
                lexical_score /= max_lexical_score

            candidate["final_score"] = (
                self.semantic_weight * candidate["semantic_score"] + self.lexical_weight * lexical_score
            )

        results = list(candidates.values())

        results.sort(key=lambda result: result["final_score"], reverse=True)

        return results[:limit]

    def _semantic_score(self, result):
        distance = result.get("distance")

        if distance is None:
            return 0.0

        return 1.0 / (1.0 + distance)
