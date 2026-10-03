import hashlib
from pathlib import Path


def create_chunks(entities):
    chunks = []

    for entity in entities:
        file_path = Path(entity["file"])

        source_lines = file_path.read_text(
            encoding="utf-8"
        ).splitlines()

        start = entity["start_line"] - 1
        end = entity["end_line"]

        source = "\n".join(source_lines[start:end])

        chunk_id_source = (
            f"{entity['file']}:"
            f"{entity['type']}:"
            f"{entity['name']}:"
            f"{entity['start_line']}:"
            f"{entity['end_line']}"
        )

        chunk_id = hashlib.sha256(
            chunk_id_source.encode("utf-8")
        ).hexdigest()

        chunks.append({
            "id": chunk_id,
            "type": entity["type"],
            "name": entity["name"],
            "file": entity["file"],
            "start_line": entity["start_line"],
            "end_line": entity["end_line"],
            "source": source,
        })

    return chunks