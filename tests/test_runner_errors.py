from sandbox.runner import SandboxRunner, SandboxCommandError


class FakeSandboxRunner(SandboxRunner):
    def __init__(self, results):
        super().__init__("unused")
        self.results = results
        self.commands = []

    def run_command_in_sandbox(self, command):
        self.commands.append(list(command))
        return self.results[len(self.commands) - 1]


def success(stdout=""):
    return {
        "exit_code": 0,
        "stdout": stdout,
        "stderr": "",
    }


def failure():
    return {
        "exit_code": 128,
        "stdout": "",
        "stderr": "Simulated Git failure",
    }


def test_run_checked_returns_success():
    expected = success("command output")
    sandbox = FakeSandboxRunner([expected])

    result = sandbox.run_checked(["git", "status"])

    assert result == expected
    assert sandbox.commands == [["git", "status"]]


def test_run_checked_raises_on_failure():
    expected = failure()
    sandbox = FakeSandboxRunner([expected])

    try:
        sandbox.run_checked(["git", "status"])
    except SandboxCommandError as error:
        assert error.command == ["git", "status"]
        assert error.result == expected
        assert "Simulated Git failure" in str(error)
    else:
        assert False, "Expected SandboxCommandError"


def test_run_checked_rejects_missing_exit_code():
    sandbox = FakeSandboxRunner([
        {"stdout": "", "stderr": "Missing exit code"}
    ])

    try:
        sandbox.run_checked(["git", "status"])
    except SandboxCommandError:
        pass
    else:
        assert False, "A missing exit code must not count as success"


def test_get_diff_returns_successful_results():
    sandbox = FakeSandboxRunner([
        success(" M main.py\n"),
        success(),
        success("example patch"),
    ])

    result = sandbox.get_diff()

    assert result == {
        "changed_files": " M main.py\n",
        "git_diff": "example patch",
    }

    assert sandbox.commands == [
        ["git", "status", "--short", "--untracked-files=all"],
        ["git", "add", "-A"],
        ["git", "diff", "--cached", "--binary"],
    ]


def test_get_diff_stops_at_each_failed_command():
    expected_commands = [
        ["git", "status", "--short", "--untracked-files=all"],
        ["git", "add", "-A"],
        ["git", "diff", "--cached", "--binary"],
    ]

    for failed_index in range(len(expected_commands)):
        results = [success() for _ in expected_commands]
        results[failed_index] = failure()

        sandbox = FakeSandboxRunner(results)

        try:
            sandbox.get_diff()
        except SandboxCommandError as error:
            assert error.command == expected_commands[failed_index]
        else:
            assert False, (
                f"Expected failure at command {failed_index}"
            )


        assert sandbox.commands == expected_commands[:failed_index + 1]