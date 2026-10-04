from pathlib import Path

import pytest

from swe_agent.tools.sandboxed import make_sandboxed_tools


def list_entries(result):
    """
    Sandboxed list_dir returns a bounded result object.

    Keep extraction explicit while tolerating the name used for
    the collection field.
    """
    assert isinstance(result, dict)
    assert result.get("truncated") is False

    for key in (
        "entries",
        "items",
        "results",
    ):
        if key in result:
            return result[key]

    raise AssertionError(
        f"Unexpected list_dir result: {result!r}"
    )


def test_read_file_inside_repo(tmp_path):
    (tmp_path / "main.py").write_text(
        "print('hi')",
        encoding="utf-8",
    )

    tools = make_sandboxed_tools(tmp_path)

    assert (
        tools["read_file"]("main.py")
        == "print('hi')"
    )


def test_read_file_escape_is_blocked(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()

    outside_file = tmp_path / "outside.txt"

    outside_file.write_text(
        "secret",
        encoding="utf-8",
    )

    tools = make_sandboxed_tools(repo_root)

    with pytest.raises(ValueError):
        tools["read_file"](
            "../outside.txt"
        )


def test_create_file_escape_is_blocked(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()

    tools = make_sandboxed_tools(repo_root)

    with pytest.raises(ValueError):
        tools["create_file"](
            "../../escaped.txt",
            "malicious",
        )

    assert not (
        tmp_path / "escaped.txt"
    ).exists()


def test_edit_file_inside_repo_still_works(tmp_path):
    (tmp_path / "test.txt").write_text(
        "line 1\n"
        "line 2\n",
        encoding="utf-8",
    )

    tools = make_sandboxed_tools(tmp_path)

    tools["edit_file"](
        "test.txt",
        "line 2\n",
        "changed\n",
    )

    assert (
        (tmp_path / "test.txt").read_text(
            encoding="utf-8"
        )
        == "line 1\nchanged\n"
    )


def test_list_dir_inside_repo(tmp_path):
    (tmp_path / "a.py").write_text(
        "x",
        encoding="utf-8",
    )

    tools = make_sandboxed_tools(tmp_path)

    result = tools["list_dir"](".")
    entries = list_entries(result)

    names = {
        item["name"]
        for item in entries
    }

    assert "a.py" in names


def test_search_dir_escape_is_blocked(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()

    tools = make_sandboxed_tools(repo_root)

    with pytest.raises(ValueError):
        tools["search_dir"](
            "secret",
            "..",
        )


def test_read_rejects_sibling_with_same_prefix(
    tmp_path,
):
    repo = tmp_path / "repo"
    repo.mkdir()

    outside = tmp_path / "repo_other"
    outside.mkdir()

    (outside / "private.txt").write_text(
        "outside content",
        encoding="utf-8",
    )

    tools = make_sandboxed_tools(repo)

    with pytest.raises(ValueError):
        tools["read_file"](
            "../repo_other/private.txt"
        )


def test_create_rejects_sibling_with_same_prefix(
    tmp_path,
):
    repo = tmp_path / "repo"
    repo.mkdir()

    outside = tmp_path / "repo_other"
    outside.mkdir()

    tools = make_sandboxed_tools(repo)

    with pytest.raises(ValueError):
        tools["create_file"](
            "../repo_other/new.txt",
            "content",
        )

    assert not (
        outside / "new.txt"
    ).exists()


def test_edit_rejects_sibling_with_same_prefix(
    tmp_path,
):
    repo = tmp_path / "repo"
    repo.mkdir()

    outside = tmp_path / "repo_other"
    outside.mkdir()

    outside_file = (
        outside / "private.txt"
    )

    outside_file.write_text(
        "original\n",
        encoding="utf-8",
    )

    tools = make_sandboxed_tools(repo)

    with pytest.raises(ValueError):
        tools["edit_file"](
            "../repo_other/private.txt",
            "original\n",
            "changed\n",
        )

    assert (
        outside_file.read_text(
            encoding="utf-8"
        )
        == "original\n"
    )


def test_search_skips_symlink_to_outside_file(
    tmp_path,
):
    repo = tmp_path / "repo"
    repo.mkdir()

    (repo / "inside.txt").write_text(
        "needle inside\n",
        encoding="utf-8",
    )

    outside_file = (
        tmp_path / "outside.txt"
    )

    outside_file.write_text(
        "needle outside\n",
        encoding="utf-8",
    )

    try:
        (
            repo / "linked.txt"
        ).symlink_to(outside_file)
    except (OSError, NotImplementedError) as error:
        pytest.skip(
            f"Symlinks unavailable: {error}"
        )

    tools = make_sandboxed_tools(repo)

    result = tools["search_dir"](
        "needle",
        ".",
    )

    assert isinstance(result, dict)
    assert result["truncated"] is False

    assert result["matches"] == [
        {
            "file": "inside.txt",
            "line_number": 1,
            "content": "needle inside",
        }
    ]


def test_search_finds_nested_files_with_relative_paths(
    tmp_path,
):
    repo = tmp_path / "repo"
    source_dir = repo / "src"
    source_dir.mkdir(parents=True)

    (source_dir / "example.py").write_text(
        "first line\n"
        "needle here\n",
        encoding="utf-8",
    )

    tools = make_sandboxed_tools(repo)

    result = tools["search_dir"](
        "needle",
        ".",
    )

    assert isinstance(result, dict)
    assert result["truncated"] is False

    assert result["matches"] == [
        {
            "file": "src/example.py",
            "line_number": 2,
            "content": "needle here",
        }
    ]