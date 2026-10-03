import tree_sitter_c

from tree_sitter import Language

from swe_agent.context.parsers.tree_sitter_parser import (
    TreeSitterParser,
)


class CParser(TreeSitterParser):
    language = Language(tree_sitter_c.language())

    class_node_types = set()

    function_node_types = {
        "function_definition",
    }