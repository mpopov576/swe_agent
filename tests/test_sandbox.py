from sandbox.runner import SandboxRunner
import subprocess

import pytest

TEST_REPO = "https://github.com/octocat/Hello-World.git"

def docker_available():
    try:
        result = subprocess.run(
            ["docker", "info"],
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (
        FileNotFoundError,
        subprocess.TimeoutExpired,
    ):
        return False

    return result.returncode == 0


pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        not docker_available(),
        reason="Docker daemon is not available",
    ),
]

def test_sandbox_can_create_file():
    sandbox = SandboxRunner(TEST_REPO)
    sandbox.clone_repo()

    result = sandbox.run_command_in_sandbox(
        [
            "python",
            "-c",
            "open('hello.txt', 'w').write('hello')",
        ]
    )
    diff = sandbox.get_diff()

    sandbox.delete_dir()

    assert result["exit_code"] == 0
    assert "hello.txt" in diff["changed_files"]
    assert "hello.txt" in diff["git_diff"]


def test_sandbox_has_no_network():
    sandbox = SandboxRunner(TEST_REPO)
    sandbox.clone_repo()

    result = sandbox.run_command_in_sandbox(
        [
            "python",
            "-c",
            "import urllib.request; urllib.request.urlopen('https://example.com', timeout=5)",
        ]
    )

    sandbox.delete_dir()

    assert result["exit_code"] != 0


def test_sandbox_can_run_python():
    sandbox = SandboxRunner(TEST_REPO)
    sandbox.clone_repo()

    result = sandbox.run_command_in_sandbox(
        [
            "python",
            "-c",
            "print('hello from sandbox')",
        ]
    )

    sandbox.delete_dir()

    assert result["exit_code"] == 0
    assert "hello from sandbox" in result["stdout"]


def test_sandbox_runs_as_non_root():
    sandbox = SandboxRunner(TEST_REPO)
    sandbox.clone_repo()

    result = sandbox.run_command_in_sandbox(
        [
            "python",
            "-c",
            "import os; print(os.getuid())",
        ],
    )

    sandbox.delete_dir()

    assert result["exit_code"] == 0
    assert result["stdout"].strip() != "0"


def test_sandbox_reports_command_failure():
    sandbox = SandboxRunner(TEST_REPO)
    sandbox.clone_repo()

    result = sandbox.run_command_in_sandbox(
        [
            "python",
            "-c",
            "raise RuntimeError('intentional failure')",
        ],
    )

    sandbox.delete_dir()

    assert result["exit_code"] != 0
    assert "intentional failure" in result["stderr"]


def test_sandbox_times_out():
    sandbox = SandboxRunner(TEST_REPO)
    sandbox.clone_repo()

    result = sandbox.run_command_in_sandbox(
        [
            "python",
            "-c",
            "import time; time.sleep(70)",
        ],
    )

    sandbox.delete_dir()

    assert result["exit_code"] == -1
    assert "timed out" in result["stderr"].lower()
