import tree_sitter_go

from tree_sitter import Language

from swe_agent.context.parsers.tree_sitter_parser import (
    TreeSitterParser,
)


class GoParser(TreeSitterParser):
    language = Language(tree_sitter_go.language())

    class_node_types = set()

    function_node_types = {
        "function_declaration",
        "method_declaration",
    }