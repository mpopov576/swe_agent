import tree_sitter_c_sharp

from tree_sitter import Language

from swe_agent.context.parsers.tree_sitter_parser import (
    TreeSitterParser,
)


class CSharpParser(TreeSitterParser):
    language = Language(tree_sitter_c_sharp.language())

    class_node_types = {
        "class_declaration",
        "interface_declaration",
        "struct_declaration",
        "enum_declaration",
    }

    function_node_types = {
        "method_declaration",
        "constructor_declaration",
    }