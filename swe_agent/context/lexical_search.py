class LexicalSearch:
    def __init__(self, chunks):
        self.chunks = chunks

    def search(self, query: str, limit: int = 10):
        query_terms = self._tokenize(query)

        if not query_terms:
            return []

        results = []

        for chunk in self.chunks:
            name = chunk.get("name", "")
            source = chunk.get("source", "")

            searchable_text = (
                name + "\n" + source
            ).lower()

            matched_terms = []

            for term in query_terms:
                if term in searchable_text:
                    matched_terms.append(term)

            if not matched_terms:
                continue

            score = self._calculate_score(
                query_terms,
                matched_terms,
                searchable_text,
            )

            results.append({
                "chunk": chunk,
                "score": score,
                "matched_terms": matched_terms,
            })

        results.sort(
            key=lambda result: result["score"],
            reverse=True,
        )

        return results[:limit]

    def _tokenize(self, text: str):
        return [
            term.lower()
            for term in text.split()
            if term.strip()
        ]

    def _calculate_score(
        self,
        query_terms,
        matched_terms,
        searchable_text,
    ):
        score = 0.0

        for term in matched_terms:
            score += 1.0

            if searchable_text.count(term) > 1:
                score += 0.5

        score += len(matched_terms) / len(query_terms)

        return score