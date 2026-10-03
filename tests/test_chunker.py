from swe_agent.context.chunker import create_chunks


def test_create_chunks(tmp_path):
    file_path = tmp_path / "example.py"

    file_path.write_text(
        "class UserService:\n"
        "    def create_user(self):\n"
        "        pass\n",
        encoding="utf-8",
    )

    entities = [
        {
            "type": "class",
            "name": "UserService",
            "file": str(file_path),
            "start_line": 1,
            "end_line": 3,
        }
    ]

    chunks = create_chunks(entities)

    assert len(chunks) == 1
    assert chunks[0]["name"] == "UserService"
    assert chunks[0]["source"] == (
        "class UserService:\n"
        "    def create_user(self):\n"
        "        pass"
    )