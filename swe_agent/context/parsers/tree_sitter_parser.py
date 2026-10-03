from pathlib import Path

from tree_sitter import Language, Parser as TSParser
from swe_agent.context.parsers.base import Parser


class TreeSitterParser(Parser):
    language = None

    class_node_types = set()
    function_node_types = set()

    def __init__(self):
        if self.language is None:
            raise ValueError("Parser language is not configured")

        self._parser = TSParser(self.language)

    def parse(self, file_path: Path):
        source = file_path.read_text(encoding="utf-8")
        source_bytes = source.encode("utf-8")

        tree = self._parser.parse(source_bytes)

        entities = []

        self._walk_tree(
            tree.root_node,
            file_path,
            entities,
        )

        return entities

    def _walk_tree(self, node, file_path, entities):
        if node.type in self.class_node_types:
            entities.append(
                self._create_entity(
                    node,
                    file_path,
                    "class",
                )
            )

        elif node.type in self.function_node_types:
            entities.append(
                self._create_entity(
                    node,
                    file_path,
                    "function",
                )
            )

        for child in node.named_children:
            self._walk_tree(
                child,
                file_path,
                entities,
            )

    def _create_entity(self, node, file_path, entity_type):
        start_line = node.start_point.row + 1
        start_column = node.start_point.column + 1

        name = self._get_name(node)

        if not isinstance(name, str) or not name.strip():
            name = (
                f"<anonymous:{entity_type}"
                f"@{start_line}:{start_column}>"
            )

        return {
            "type": entity_type,
            "name": name,
            "file": str(file_path),
            "start_line": start_line,
            "end_line": node.end_point.row + 1,
        }

    def _get_name(self, node):
        name_node = node.child_by_field_name("name")

        if name_node is not None:
            return name_node.text.decode("utf-8")

        return self._get_name_from_children(node)

    def _get_name_from_children(self, node):
        for child in node.named_children:
            if child.type in {
                "identifier",
                "field_identifier",
                "type_identifier",
            }:
                return child.text.decode("utf-8")

            result = self._get_name_from_children(child)

            if result is not None:
                return result

        return None