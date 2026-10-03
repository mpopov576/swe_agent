import shutil
from pathlib import Path
from tempfile import mkdtemp
from tempfile import TemporaryDirectory

from swe_agent.tools.sandboxed import make_sandboxed_tools


def test_read_file_inside_repo():
    tmp_path = Path(mkdtemp())

    (tmp_path / "main.py").write_text("print('hi')", encoding="utf-8")

    tools = make_sandboxed_tools(tmp_path)

    assert tools["read_file"]("main.py") == "print('hi')"

    shutil.rmtree(tmp_path)


def test_read_file_escape_is_blocked():
    tmp_path = Path(mkdtemp())
    repo_root = tmp_path / "repo"
    repo_root.mkdir()

    outside_file = tmp_path / "outside.txt"
    outside_file.write_text("secret", encoding="utf-8")

    tools = make_sandboxed_tools(repo_root)

    try:
        tools["read_file"]("../outside.txt")
        assert False, "expected ValueError"
    except ValueError:
        pass

    shutil.rmtree(tmp_path)


def test_create_file_escape_is_blocked():
    tmp_path = Path(mkdtemp())
    repo_root = tmp_path / "repo"
    repo_root.mkdir()

    tools = make_sandboxed_tools(repo_root)

    try:
        tools["create_file"]("../../escaped.txt", "malicious")
        assert False, "expected ValueError"
    except ValueError:
        pass

    assert not (tmp_path / "escaped.txt").exists()

    shutil.rmtree(tmp_path)


def test_edit_file_inside_repo_still_works():
    tmp_path = Path(mkdtemp())

    (tmp_path / "test.txt").write_text("line 1\nline 2\n", encoding="utf-8")

    tools = make_sandboxed_tools(tmp_path)

    tools["edit_file"]("test.txt", start_line=2, end_line=2, replacement="changed")

    assert (tmp_path / "test.txt").read_text() == "line 1\nchanged\n"

    shutil.rmtree(tmp_path)


def test_list_dir_inside_repo():
    tmp_path = Path(mkdtemp())

    (tmp_path / "a.py").write_text("x", encoding="utf-8")

    tools = make_sandboxed_tools(tmp_path)
    names = {item["name"] for item in tools["list_dir"](".")}

    assert "a.py" in names

    shutil.rmtree(tmp_path)


def test_search_dir_escape_is_blocked():
    tmp_path = Path(mkdtemp())
    repo_root = tmp_path / "repo"
    repo_root.mkdir()

    tools = make_sandboxed_tools(repo_root)

    try:
        tools["search_dir"]("secret", "..")
        assert False, "expected ValueError"
    except ValueError:
        pass

    shutil.rmtree(tmp_path)


def test_read_rejects_sibling_with_same_prefix():
    with TemporaryDirectory() as directory:
        base = Path(directory)
        repo = base / "repo"
        repo.mkdir()

        outside = base / "repo_other"
        outside.mkdir()
        (outside / "private.txt").write_text(
            "outside content", encoding="utf-8"
        )

        tools = make_sandboxed_tools(repo)

        try:
            tools["read_file"]("../repo_other/private.txt")
        except ValueError:
            pass
        else:
            assert False, "Reading outside the repository was allowed"


def test_create_rejects_sibling_with_same_prefix():
    with TemporaryDirectory() as directory:
        base = Path(directory)
        repo = base / "repo"
        repo.mkdir()

        outside = base / "repo_other"
        outside.mkdir()

        tools = make_sandboxed_tools(repo)

        try:
            tools["create_file"]("../repo_other/new.txt", "content")
        except ValueError:
            pass
        else:
            assert False, "Creating a file outside the repo was allowed"

        assert not (outside / "new.txt").exists()


def test_edit_rejects_sibling_with_same_prefix():
    with TemporaryDirectory() as directory:
        base = Path(directory)
        repo = base / "repo"
        repo.mkdir()

        outside = base / "repo_other"
        outside.mkdir()

        outside_file = outside / "private.txt"
        outside_file.write_text("original\n", encoding="utf-8")

        tools = make_sandboxed_tools(repo)

        try:
            tools["edit_file"](
                "../repo_other/private.txt",
                start_line=1,
                end_line=1,
                replacement="changed",
            )
        except ValueError:
            pass
        else:
            assert False, "Editing outside the repository was allowed"

        assert outside_file.read_text(encoding="utf-8") == "original\n"


def test_search_skips_symlink_to_outside_file():
    with TemporaryDirectory() as directory:
        base = Path(directory)
        repo = base / "repo"
        repo.mkdir()

        (repo / "inside.txt").write_text(
            "needle inside\n", encoding="utf-8"
        )

        outside_file = base / "outside.txt"
        outside_file.write_text(
            "needle outside\n", encoding="utf-8"
        )

        try:
            (repo / "linked.txt").symlink_to(outside_file)
        except (OSError, NotImplementedError) as error:
            print(f"SKIPPED: symlink test — {error}")
            return False

        tools = make_sandboxed_tools(repo)
        results = tools["search_dir"]("needle", ".")

        assert results == [
            {
                "file": "inside.txt",
                "line_number": 1,
                "content": "needle inside",
            }
        ]


def test_search_finds_nested_files_with_relative_paths():
    with TemporaryDirectory() as directory:
        repo = Path(directory) / "repo"
        source_dir = repo / "src"
        source_dir.mkdir(parents=True)

        (source_dir / "example.py").write_text(
            "first line\nneedle here\n",
            encoding="utf-8",
        )

        tools = make_sandboxed_tools(repo)
        results = tools["search_dir"]("needle", ".")

        assert results == [
            {
                "file": "src/example.py",
                "line_number": 2,
                "content": "needle here",
            }
        ]