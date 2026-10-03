import re


def populate_dependency_graph(chunks: list[dict], dependency_graph) -> None:
    name_to_ids: dict[str, list[str]] = {}

    for chunk in chunks:
        name_to_ids.setdefault(chunk["name"], []).append(chunk["id"])

    for chunk in chunks:
        source = chunk["source"]

        for name, target_ids in name_to_ids.items():
            if not re.search(rf"\b{re.escape(name)}\s*\(", source):
                continue

            for target_id in target_ids:
                if target_id == chunk["id"]:
                    continue

                dependency_graph.add_dependency(chunk["id"], target_id, "calls")