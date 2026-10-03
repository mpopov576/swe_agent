class DependencyGraph:
    def __init__(self):
        self._edges = {}

    def add_dependency(
            self,
            source_id: str,
            target_id: str,
            dependency_type: str,
    ):
        if source_id not in self._edges:
            self._edges[source_id] = []

        self._edges[source_id].append({
            "target": target_id,
            "type": dependency_type,
        })

    def get_dependencies(self, chunk_id: str):
        return self._edges.get(chunk_id, [])

    def get_dependents(self, chunk_id: str):
        dependents = []

        for source_id, edges in self._edges.items():
            for edge in edges:
                if edge["target"] == chunk_id:
                    dependents.append(
                        {
                            "source": source_id,
                            "type": edge["type"]
                        }
                    )

        return dependents

    def expand(self, chunk_ids: list[str], depth: int = 1):
        visited = set(chunk_ids)
        current = set(chunk_ids)

        for _ in range(depth):
            next_chunks = set()

            for chunk_id in current:
                for edge in self.get_dependencies(chunk_id):
                    target = edge["target"]

                    if target not in visited:
                        visited.add(target)
                        next_chunks.add(target)

            current = next_chunks

            if not current:
                break

        return list(visited)