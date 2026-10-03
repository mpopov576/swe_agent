import os
from pathlib import Path


IGNORED_DIRECTORIES = {
    ".git",
    ".venv",
    "venv",
    "__pycache__",
    "node_modules",
    "dist",
    "build",
}


def discover_files(repository_path):
    root = Path(repository_path).resolve()

    if not root.is_dir():
        raise NotADirectoryError(repository_path)

    files = []
    total_bytes = 0
    visited = 0

    for directory, subdirs, names in os.walk(
        root,
        followlinks=False,
    ):
        # Prune ignored directories before descending.
        subdirs[:] = sorted(
            name
            for name in subdirs
            if name not in IGNORED_DIRECTORIES
            and not (
                Path(directory) / name
            ).is_symlink()
        )

        visited += len(subdirs) + len(names)

        if visited > 20_000:
            raise ValueError(
                "Repository has too many directory entries"
            )

        for name in sorted(names):
            path = Path(directory) / name

            # Do not index symlink targets or special files.
            if path.is_symlink() or not path.is_file():
                continue

            size = path.stat().st_size

            # Large files are excluded from retrieval.
            if size > 1_000_000:
                continue

            total_bytes += size
            files.append(path)

            if (
                len(files) > 2_000
                or total_bytes > 100_000_000
            ):
                raise ValueError(
                    "Repository exceeds the indexing budget"
                )

    return sorted(files)