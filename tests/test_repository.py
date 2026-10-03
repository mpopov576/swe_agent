from swe_agent.context.repository import discover_files


def test_discover_files(tmp_path):
    (tmp_path / "main.py").write_text(
        "print('hello')",
        encoding="utf-8",
    )

    (tmp_path / "utils.py").write_text(
        "def hello(): pass",
        encoding="utf-8",
    )

    files = discover_files(str(tmp_path))

    assert tmp_path / "main.py" in files
    assert tmp_path / "utils.py" in files