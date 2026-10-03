from pathlib import Path
from tempfile import mkdtemp
import subprocess

from swe_agent.context.index import build_index
from swe_agent.context.dependency_graph import DependencyGraph
from swe_agent.context.call_detection import populate_dependency_graph


def make_repo(files: dict) -> Path:
    repo_path = Path(mkdtemp()) / "repo"
    repo_path.mkdir(parents=True)

    subprocess.run(["git", "init", "-q"], cwd=repo_path, check=True)
    subprocess.run(["git", "config", "user.email", "a@a.com"], cwd=repo_path, check=True)
    subprocess.run(["git", "config", "user.name", "a"], cwd=repo_path, check=True)

    for name, content in files.items():
        (repo_path / name).write_text(content, encoding="utf-8")

    subprocess.run(["git", "add", "-A"], cwd=repo_path, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "init"], cwd=repo_path, check=True)

    return repo_path


def get_chunk(chunks, name):
    return next(c for c in chunks if c["name"] == name)


def test_detects_direct_call_between_two_functions():
    repo_path = make_repo({
        "users.py": (
            "def create_user(name):\n"
            "    save_user(name)\n\n"
            "def save_user(name):\n"
            "    pass\n"
        ),
    })

    chunks = build_index(str(repo_path))
    graph = DependencyGraph()
    populate_dependency_graph(chunks, graph)

    create_user = get_chunk(chunks, "create_user")
    save_user = get_chunk(chunks, "save_user")

    deps = graph.get_dependencies(create_user["id"])
    assert any(d["target"] == save_user["id"] for d in deps)


def test_no_edge_when_function_never_called():
    repo_path = make_repo({
        "users.py": (
            "def create_user(name):\n"
            "    pass\n\n"
            "def unused_helper():\n"
            "    pass\n"
        ),
    })

    chunks = build_index(str(repo_path))
    graph = DependencyGraph()
    populate_dependency_graph(chunks, graph)

    create_user = get_chunk(chunks, "create_user")
    unused_helper = get_chunk(chunks, "unused_helper")

    deps = graph.get_dependencies(create_user["id"])
    assert not any(d["target"] == unused_helper["id"] for d in deps)


def test_detects_call_across_two_files():
    repo_path = make_repo({
        "handlers.py": (
            "def handle_request(name):\n"
            "    save_user(name)\n"
        ),
        "db.py": (
            "def save_user(name):\n"
            "    pass\n"
        ),
    })

    chunks = build_index(str(repo_path))
    graph = DependencyGraph()
    populate_dependency_graph(chunks, graph)

    handle_request = get_chunk(chunks, "handle_request")
    save_user = get_chunk(chunks, "save_user")

    deps = graph.get_dependencies(handle_request["id"])
    assert any(d["target"] == save_user["id"] for d in deps)


def test_does_not_add_self_dependency_for_recursive_function():
    repo_path = make_repo({
        "math_utils.py": (
            "def factorial(n):\n"
            "    if n <= 1:\n"
            "        return 1\n"
            "    return n * factorial(n - 1)\n"
        ),
    })

    chunks = build_index(str(repo_path))
    graph = DependencyGraph()
    populate_dependency_graph(chunks, graph)

    factorial = get_chunk(chunks, "factorial")

    deps = graph.get_dependencies(factorial["id"])
    assert not any(d["target"] == factorial["id"] for d in deps)


def test_partial_name_does_not_falsely_match():
    repo_path = make_repo({
        "users.py": (
            "def save_user(name):\n"
            "    pass\n\n"
            "def save_user_profile(name):\n"
            "    save_user(name)\n"
        ),
    })

    chunks = build_index(str(repo_path))
    graph = DependencyGraph()
    populate_dependency_graph(chunks, graph)

    save_user = get_chunk(chunks, "save_user")
    save_user_profile = get_chunk(chunks, "save_user_profile")

    deps = graph.get_dependencies(save_user_profile["id"])
    assert any(d["target"] == save_user["id"] for d in deps)

    deps_reverse = graph.get_dependencies(save_user["id"])
    assert not any(d["target"] == save_user_profile["id"] for d in deps_reverse)


if __name__ == "__main__":
    tests = [
        test_detects_direct_call_between_two_functions,
        test_no_edge_when_function_never_called,
        test_detects_call_across_two_files,
        test_does_not_add_self_dependency_for_recursive_function,
        test_partial_name_does_not_falsely_match,
    ]

    for test in tests:
        test()
        print(f"PASSED: {test.__name__}")

    print(f"\nAll {len(tests)} tests passed.")