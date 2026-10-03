import tree_sitter_typescript

from tree_sitter import Language

from swe_agent.context.parsers.tree_sitter_parser import (
    TreeSitterParser,
)


class TypeScriptParser(TreeSitterParser):
    language = Language(tree_sitter_typescript.language_typescript())

    class_node_types = {
        "class_declaration",
    }

    function_node_types = {
        "function_declaration",
        "method_definition",
        "arrow_function",
    }