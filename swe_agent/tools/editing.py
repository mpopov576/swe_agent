import re
from pathlib import Path


def read_file(path: str):
    return Path(path).read_text(encoding="utf-8")


def edit_file(path: str, old_text: str, new_text: str):
    if not isinstance(old_text, str) or not isinstance(new_text, str):
        raise ValueError("old_text and new_text must be strings")

    old_text = old_text.replace("\r\n", "\n")
    new_text = new_text.replace("\r\n", "\n")

    if not old_text:
        raise ValueError("old_text must not be empty")

    if old_text == new_text:
        raise ValueError("No change: old_text and new_text are identical")

    file_path = Path(path)
    content = file_path.read_bytes().decode("utf-8")

    # Match literal text, allowing LF or CRLF at each newline.
    pattern = re.compile(
        r"\r?\n".join(
            re.escape(part)
            for part in old_text.split("\n")
        )
    )

    match = pattern.search(content)

    if match is None:
        raise ValueError(
            "old_text was not found. Read the file and copy its exact text."
        )

    if pattern.search(content, match.start() + 1) is not None:
        raise ValueError(
            "old_text matches more than once. Include more surrounding code."
        )

    existing = match.group()

    if "\n" in existing:
        first_newline = existing.index("\n")
        newline = (
            "\r\n"
            if existing[first_newline - 1:first_newline] == "\r"
            else "\n"
        )
    else:
        crlf_count = content.count("\r\n")
        lf_count = content.count("\n") - crlf_count
        newline = "\r\n" if crlf_count > lf_count else "\n"

    replacement = new_text.replace("\n", newline)
    updated = (
        content[:match.start()]
        + replacement
        + content[match.end():]
    )

    file_path.write_bytes(updated.encode("utf-8"))


def create_file(path: str, content: str = ""):
    file_path = Path(path)
    file_path.parent.mkdir(parents=True, exist_ok=True)

    with file_path.open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(content)