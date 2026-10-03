import tree_sitter_java

from tree_sitter import Language

from swe_agent.context.parsers.tree_sitter_parser import (
    TreeSitterParser,
)


class JavaParser(TreeSitterParser):
    language = Language(tree_sitter_java.language())

    class_node_types = {
        "class_declaration",
        "interface_declaration",
        "enum_declaration",
    }

    function_node_types = {
        "method_declaration",
        "constructor_declaration",
    }