from pathlib import Path

def list_dir(directory: str):
    path = Path(directory)

    if not path.exists():
        raise FileNotFoundError(f"Directory {path} does not exist")

    if not path.is_dir():
        raise NotADirectoryError(f"Directory {path} is not a directory")

    return [
        {
            "name": item.name,
            "type": "directory" if item.is_dir() else "file"
        }

        for item in sorted(path.iterdir(), key=lambda item: item.name.lower())
    ]


def goto_line(path: str, line_number: int):
    file_path = Path(path)

    if not file_path.exists():
        raise FileNotFoundError(f"File {file_path} does not exist")

    if not file_path.is_file():
        raise FileNotFoundError(f"File {file_path} is not a file")

    if line_number < 1:
        raise IndexError(f"Line {line_number} is out of range")

    lines = file_path.read_text(encoding="utf-8").splitlines()

    if line_number > len(lines):
        raise IndexError(f"Line {line_number} is out of range")

    return {
        "line_number": line_number,
        "content": lines[line_number - 1],
    }

