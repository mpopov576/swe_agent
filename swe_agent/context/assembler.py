from swe_agent.limits import CONTEXT_LIMIT, clip


class ContextAssembler:
    def __init__(
        self,
        dependency_graph=None,
        chunks_by_id=None,
    ):
        self.dependency_graph = dependency_graph
        self.chunks_by_id = chunks_by_id or {}

    def assemble(
        self,
        reranked_results: list[dict],
        dependency_depth: int = 1,
    ):
        selected_ids = [
            result["chunk"]["id"]
            for result in reranked_results
        ]

        context_ids = list(selected_ids)

        if self.dependency_graph is not None:
            expanded_ids = self.dependency_graph.expand(
                selected_ids,
                depth=dependency_depth,
            )

            for chunk_id in expanded_ids:
                if chunk_id not in context_ids:
                    context_ids.append(chunk_id)

        context_chunks = []

        for chunk_id in context_ids:
            chunk = self.chunks_by_id.get(chunk_id)

            if chunk is None:
                continue

            context_chunks.append(chunk)

        return self._format_context(context_chunks)

    def _format_context(self, chunks):
        sections = []
        used = 0

        for chunk in chunks:
            section = (
                f"File: {chunk['file']}\n"
                f"Lines: "
                f"{chunk['start_line']}-{chunk['end_line']}\n"
                f"Type: {chunk['type']}\n"
                f"Name: {chunk['name']}\n\n"
                f"{chunk['source']}"
            )

            remaining = CONTEXT_LIMIT - used

            sections.append(
                clip(section, remaining)
            )

            # Account for the separator between sections.
            used += len(sections[-1]) + 7

            if used >= CONTEXT_LIMIT:
                break

        return clip(
            "\n\n---\n\n".join(sections),
            CONTEXT_LIMIT,
        )