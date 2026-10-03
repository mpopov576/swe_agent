import tree_sitter_rust

from tree_sitter import Language

from swe_agent.context.parsers.tree_sitter_parser import (
    TreeSitterParser,
)


class RustParser(TreeSitterParser):
    language = Language(tree_sitter_rust.language())

    class_node_types = {
        "struct_item",
        "enum_item",
        "trait_item",
    }

    function_node_types = {
        "function_item",
    }