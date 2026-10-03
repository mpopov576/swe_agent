import os
from pathlib import Path

from swe_agent.context.repository import discover_files
from swe_agent.limits import clip
from swe_agent.tools.editing import create_file, edit_file


FILE_LIMIT = 1_000_000
MATCH_LIMIT = 100


def confine(repo_root, path):
    root = Path(repo_root).resolve()
    resolved = (root / path).resolve()

    if not resolved.is_relative_to(root):
        raise ValueError(f"Path escapes repository root: {path}")

    if ".git" in resolved.relative_to(root).parts:
        raise ValueError("Direct access to Git metadata is not allowed")

    return str(resolved)


def make_sandboxed_tools(repo_root):
    root = Path(repo_root).resolve()

    def safe_file(path):
        file = Path(confine(root, path))

        if not file.is_file():
            raise FileNotFoundError(path)

        if file.stat().st_size > FILE_LIMIT:
            raise ValueError("File exceeds the 1 MB tool limit")

        return file

    def text(path):
        with safe_file(path).open("r", encoding="utf-8") as stream:
            content = stream.read(FILE_LIMIT + 1)

        if len(content) > FILE_LIMIT:
            raise ValueError("File grew beyond the tool limit")

        return content

    def read(path):
        return clip(text(path))

    def edit(path, old_text, new_text):
        file = safe_file(path)

        if len(new_text.encode("utf-8")) + file.stat().st_size > FILE_LIMIT:
            raise ValueError("Edit exceeds the file limit")

        edit_file(str(file), old_text, new_text)
        return {"edited": path}

    def create(path, content=""):
        if len(content.encode("utf-8")) > FILE_LIMIT:
            raise ValueError("Content exceeds the file limit")

        create_file(confine(root, path), content)
        return {"created": path}

    def listing(directory):
        entries = []
        truncated = False

        with os.scandir(confine(root, directory)) as iterator:
            for entry in iterator:
                if len(entries) == 200:
                    truncated = True
                    break

                entries.append({
                    "name": clip(entry.name, 300),
                    "type": (
                        "directory"
                        if entry.is_dir(follow_symlinks=False)
                        else "file"
                    ),
                })

        return {"entries": entries, "truncated": truncated}

    def goto(path, line_number):
        lines = text(path).splitlines()

        if not 1 <= line_number <= len(lines):
            raise IndexError("Line is out of range")

        return {
            "line_number": line_number,
            "content": clip(lines[line_number - 1]),
        }

    def matches(search_term, file_path):
        if not search_term:
            raise ValueError("Search term must not be empty")

        result = []

        for number, line in enumerate(text(file_path).splitlines(), 1):
            if search_term in line:
                if len(result) == MATCH_LIMIT:
                    return {"matches": result, "truncated": True}

                result.append({
                    "line_number": number,
                    "content": clip(line, 500),
                })

        return {"matches": result, "truncated": False}

    def search_directory(search_term, directory):
        results = []
        truncated = False

        for file in discover_files(confine(root, directory)):
            try:
                found = matches(search_term, str(file))
            except (UnicodeDecodeError, OSError):
                continue

            truncated |= found["truncated"]

            for match in found["matches"]:
                if len(results) == MATCH_LIMIT:
                    return {"matches": results, "truncated": True}

                results.append({
                    "file": file.relative_to(root).as_posix(),
                    **match,
                })

        return {"matches": results, "truncated": truncated}

    return {
        "read_file": read,
        "edit_file": edit,
        "create_file": create,
        "list_dir": listing,
        "goto_line": goto,
        "search_file": matches,
        "search_dir": search_directory,
    }