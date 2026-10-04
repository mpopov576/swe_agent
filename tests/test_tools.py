import pytest

from swe_agent.tools.navigation import (
    goto_line,
    list_dir,
)
from swe_agent.tools.search import (
    search_dir,
    search_file,
)
from swe_agent.tools.editing import (
    create_file,
    edit_file,
    read_file,
)


def test_list_dir(tmp_path):
    (tmp_path / "file.txt").write_text(
        "hello",
        encoding="utf-8",
    )
    (tmp_path / "folder").mkdir()

    result = list_dir(str(tmp_path))

    names = {
        item["name"]
        for item in result
    }

    assert "file.txt" in names
    assert "folder" in names


def test_goto_line(tmp_path):
    file_path = tmp_path / "test.txt"

    file_path.write_text(
        "line 1\n"
        "line 2\n"
        "line 3",
        encoding="utf-8",
    )

    result = goto_line(
        str(file_path),
        3,
    )

    assert result["line_number"] == 3
    assert result["content"] == "line 3"


def test_search_file(tmp_path):
    file_path = tmp_path / "test.py"

    file_path.write_text(
        "def hello():\n"
        "    print('hello')\n"
        "def goodbye():\n",
        encoding="utf-8",
    )

    result = search_file(
        "hello",
        str(file_path),
    )

    assert len(result) == 2
    assert result[0]["line_number"] == 1
    assert result[1]["line_number"] == 2


def test_search_dir(tmp_path):
    file1 = tmp_path / "one.py"
    file2 = tmp_path / "two.py"

    file1.write_text(
        "hello world",
        encoding="utf-8",
    )
    file2.write_text(
        "hello again",
        encoding="utf-8",
    )

    result = search_dir(
        "hello",
        str(tmp_path),
    )

    assert len(result) == 2


def test_read_file(tmp_path):
    file_path = tmp_path / "test.txt"

    file_path.write_text(
        "hello",
        encoding="utf-8",
    )

    result = read_file(
        str(file_path)
    )

    assert result == "hello"


def test_edit_file(tmp_path):
    file_path = tmp_path / "test.txt"

    file_path.write_text(
        "line 1\n"
        "line 2\n"
        "line 3\n",
        encoding="utf-8",
    )

    edit_file(
        str(file_path),
        "line 2\n",
        "changed line\n",
    )

    result = file_path.read_text(
        encoding="utf-8"
    )

    assert result == (
        "line 1\n"
        "changed line\n"
        "line 3\n"
    )


def test_edit_file_rejects_missing_text(tmp_path):
    file_path = tmp_path / "test.txt"

    file_path.write_text(
        "original\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError):
        edit_file(
            str(file_path),
            "does not exist",
            "replacement",
        )


def test_create_file(tmp_path):
    file_path = tmp_path / "new_file.txt"

    create_file(
        str(file_path),
        "hello world",
    )

    assert file_path.exists()
    assert (
        file_path.read_text(encoding="utf-8")
        == "hello world"
    )


def test_create_file_cannot_overwrite(tmp_path):
    file_path = tmp_path / "existing.txt"

    file_path.write_text(
        "original",
        encoding="utf-8",
    )

    with pytest.raises(FileExistsError):
        create_file(
            str(file_path),
            "replacement",
        )