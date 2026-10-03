import tree_sitter_javascript

from tree_sitter import Language

from swe_agent.context.parsers.tree_sitter_parser import (
    TreeSitterParser,
)


class JavaScriptParser(TreeSitterParser):
    language = Language(tree_sitter_javascript.language())

    class_node_types = {
        "class_declaration",
    }

    function_node_types = {
        "function_declaration",
        "method_definition",
        "arrow_function",
    }