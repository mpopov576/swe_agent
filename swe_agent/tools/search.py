from pathlib import Path


def search_file(search_term: str, file_path: str):
    path = Path(file_path)

    if not path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    if not path.is_file():
        raise IsADirectoryError(f"Not a file: {file_path}")

    results = []

    for line_number, line in enumerate(
        path.read_text(encoding="utf-8").splitlines(),
        start=1
    ):
        if search_term in line:
            results.append(
                {
                    "line_number": line_number,
                    "content": line
                }
            )

    return results



def search_dir(search_term: str, directory: str):
    path = Path(directory)

    if not path.exists():
        raise FileNotFoundError(f"Directory not found: {directory}")

    if not path.is_dir():
        raise NotADirectoryError(f"Not a directory: {directory}")

    results = []

    for file_path in path.rglob("*"):
        if not file_path.is_file():
            continue

        try:
            lines = file_path.read_text(encoding="utf-8").splitlines()
        except UnicodeDecodeError:
            continue

        for line_number, line in enumerate(lines, start=1):
            if search_term in line:
                results.append({
                    "file": str(file_path),
                    "line_number": line_number,
                    "content": line,
                })

    return results
