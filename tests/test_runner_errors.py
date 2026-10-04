import pytest

from sandbox.runner import SandboxCommandError, SandboxRunner


class FakeSandboxRunner(SandboxRunner):
    def __init__(self, results):
        super().__init__("unused")
        self.results = results
        self.commands = []

    def run_command_in_sandbox(
        self,
        command,
        *,
        read_only=False,
        output_limit=32_768,
    ):
        self.commands.append(list(command))
        return self.results[len(self.commands) - 1]


def success(stdout=""):
    return {
        "exit_code": 0,
        "stdout": stdout,
        "stderr": "",
        "stdout_truncated": False,
        "stderr_truncated": False,
        "capture_error": None,
    }


def failure():
    return {
        "exit_code": 128,
        "stdout": "",
        "stderr": "Simulated Git failure",
        "stdout_truncated": False,
        "stderr_truncated": False,
        "capture_error": None,
    }


def test_run_checked_returns_success():
    expected = success("command output")
    sandbox = FakeSandboxRunner([expected])

    result = sandbox.run_checked(["git", "status"])

    assert result == expected
    assert sandbox.commands == [
        ["git", "status"],
    ]


def test_run_checked_raises_on_failure():
    expected = failure()
    sandbox = FakeSandboxRunner([expected])

    with pytest.raises(SandboxCommandError) as exc_info:
        sandbox.run_checked(["git", "status"])

    error = exc_info.value

    assert error.command == ["git", "status"]
    assert error.result == expected
    assert "Simulated Git failure" in str(error)


def test_run_checked_rejects_missing_exit_code():
    sandbox = FakeSandboxRunner([
        {
            "stdout": "",
            "stderr": "Missing exit code",
        }
    ])

    with pytest.raises(SandboxCommandError):
        sandbox.run_checked(["git", "status"])


def test_get_diff_returns_successful_results():
    sandbox = FakeSandboxRunner([
        success(),
        success(" M main.py\n"),
        success("example patch"),
    ])

    result = sandbox.get_diff()

    assert result == {
        "changed_files": " M main.py\n",
        "git_diff": "example patch",
    }

    assert len(sandbox.commands) == 3

    # 1. Stage all changes.
    assert sandbox.commands[0] == [
        "git",
        "add",
        "-A",
    ]

    # 2. Collect the changed-file summary.
    names_command = sandbox.commands[1]

    assert names_command[:3] == [
        "git",
        "diff",
        "--cached",
    ]

    assert "--no-color" in names_command
    assert "--no-ext-diff" in names_command
    assert "--no-textconv" in names_command
    assert "--name-status" in names_command
    assert "--binary" not in names_command

    # 3. Capture the actual binary-safe patch.
    patch_command = sandbox.commands[2]

    assert patch_command[:3] == [
        "git",
        "diff",
        "--cached",
    ]

    assert "--no-color" in patch_command
    assert "--no-ext-diff" in patch_command
    assert "--no-textconv" in patch_command
    assert "--binary" in patch_command
    assert "--full-index" in patch_command
    assert "--name-status" not in patch_command


def test_get_diff_stops_at_each_failed_command():
    # First discover the command sequence used by the current
    # implementation. This keeps the test focused on the
    # important contract: every failed Git command must stop
    # get_diff immediately and surface SandboxCommandError.
    probe = FakeSandboxRunner([
        success(),
        success(),
        success(),
    ])

    probe.get_diff()

    expected_commands = probe.commands

    assert len(expected_commands) == 3

    for failed_index in range(len(expected_commands)):
        results = [
            success()
            for _ in expected_commands
        ]
        results[failed_index] = failure()

        sandbox = FakeSandboxRunner(results)

        with pytest.raises(SandboxCommandError) as exc_info:
            sandbox.get_diff()

        assert (
            exc_info.value.command
            == expected_commands[failed_index]
        )

        assert sandbox.commands == expected_commands[
            :failed_index + 1
        ]