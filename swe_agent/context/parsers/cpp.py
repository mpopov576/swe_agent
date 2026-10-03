import tree_sitter_cpp

from tree_sitter import Language

from swe_agent.context.parsers.tree_sitter_parser import (
    TreeSitterParser,
)


class CppParser(TreeSitterParser):
    language = Language(tree_sitter_cpp.language())

    class_node_types = {
        "class_specifier",
        "struct_specifier",
    }

    function_node_types = {
        "function_definition",
    }