from pathlib import Path
from tempfile import TemporaryDirectory

from sandbox.docker_executor import run_in_docker
from swe_agent.limits import Incomplete, bounded_process


ERROR_FLAGS = (
    "error", "timed_out", "capture_error", "cleanup_failed",
    "stdout_truncated", "stderr_truncated",
)


def complete_result(result):
    return (
        isinstance(result, dict)
        and isinstance(result.get("exit_code"), int)
        and not any(result.get(flag) for flag in ERROR_FLAGS)
    )


def shows_improvement(comparison):
    """Reject incomplete runs and common setup failures."""
    if not isinstance(comparison, dict):
        return False

    before = comparison.get("before")
    after = comparison.get("after")

    if not complete_result(before) or not complete_result(after):
        return False

    if not (
        0 < before["exit_code"] < 125
        and after["exit_code"] == 0
    ):
        return False

    output = (
        before.get("stdout", "") + "\n" + before.get("stderr", "")
    ).lower()

    setup_errors = (
        "can't open file",
        "cannot open file",
        "no such file or directory",
        "file or directory not found",
        "command not found",
        "modulenotfounderror",
        "cannot find module",
        "cannot find package",
        "no tests ran",
        "no tests collected",
        "ran 0 tests",
        "collected 0 items",
    )

    return not any(error in output for error in setup_errors)

def verify_fix(sandbox, command):
    """Run the same language-neutral command on original and patched code."""
    if (
        not isinstance(command, list)
        or not command
        or any(not isinstance(argument, str) for argument in command)
        or not command[0].strip()
    ):
        raise ValueError("command must be a nonempty list of strings")

    if not sandbox.base_commit:
        raise Incomplete("verification_incomplete", "Original commit is unknown")

    def git(arguments):
        result = bounded_process(
            ["git", "-c", "core.autocrlf=false", *arguments],
            timeout=sandbox.deadline.remaining(60),
        )
        if result.get("exit_code") != 0:
            raise Incomplete(
                "verification_incomplete",
                result.get("stderr") or "Could not prepare original checkout",
            )

    def run(directory):
        result = run_in_docker(
            command,
            directory,
            image_name=sandbox.image_name,
            timeout=sandbox.deadline.remaining(60),
            output_limit=32_768,
            read_only=True,
        )
        if result.get("cleanup_failed"):
            sandbox.cleanup_failed = True
            raise Incomplete("cleanup_failed", result.get("stderr", ""))
        return result

    with TemporaryDirectory(prefix="swe-verification-") as directory:
        original = Path(directory) / "original"
        git([
            "clone", "--no-local", "--no-checkout",
            str(sandbox.repo_path), str(original),
        ])
        git(["-C", str(original), "checkout", "--detach", sandbox.base_commit])

        before = run(original)
        after = run(sandbox.repo_path)

    return {"command": list(command), "before": before, "after": after}
