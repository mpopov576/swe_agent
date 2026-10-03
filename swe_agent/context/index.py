from swe_agent.context.repository import discover_files
from swe_agent.context.chunker import create_chunks

from swe_agent.context.parsers.python import PythonParser
from swe_agent.context.parsers.javascript import JavaScriptParser
from swe_agent.context.parsers.typescript import TypeScriptParser
from swe_agent.context.parsers.java import JavaParser
from swe_agent.context.parsers.c import CParser
from swe_agent.context.parsers.cpp import CppParser
from swe_agent.context.parsers.go import GoParser
from swe_agent.context.parsers.rust import RustParser
from swe_agent.context.parsers.csharp import CSharpParser


PARSERS = {
    ".py": PythonParser(),
    ".js": JavaScriptParser(),
    ".jsx": JavaScriptParser(),
    ".ts": TypeScriptParser(),
    ".tsx": TypeScriptParser(),
    ".java": JavaParser(),
    ".c": CParser(),
    ".h": CParser(),
    ".cpp": CppParser(),
    ".cc": CppParser(),
    ".cxx": CppParser(),
    ".hpp": CppParser(),
    ".go": GoParser(),
    ".rs": RustParser(),
    ".cs": CSharpParser(),
}


def build_index(repository_path: str):
    chunks = []

    files = discover_files(repository_path)

    for file_path in files:
        parser = PARSERS.get(file_path.suffix.lower())

        if parser is None:
            continue

        entities = parser.parse(file_path)

        file_chunks = create_chunks(entities)

        chunks.extend(file_chunks)

    return chunks