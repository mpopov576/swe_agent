import tree_sitter_python

from tree_sitter import Language

from swe_agent.context.parsers.tree_sitter_parser import (
    TreeSitterParser,
)


class PythonParser(TreeSitterParser):
    language = Language(tree_sitter_python.language())

    class_node_types = {
        "class_definition",
    }

    function_node_types = {
        "function_definition",
    }