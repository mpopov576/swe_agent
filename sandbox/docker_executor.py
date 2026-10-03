import sys
from pathlib import Path
from uuid import uuid4

from swe_agent.limits import bounded_process, clip


DOCKER_IMAGE = "evolving-swe-sandbox:1.0"
COMMAND_TIMEOUT_SECONDS = 60
CLEANUP_TIMEOUT_SECONDS = 15


def _remove_container(container_name):
    try:
        result = bounded_process(
            [
                "docker",
                "rm",
                "--force",
                container_name,
            ],
            timeout=CLEANUP_TIMEOUT_SECONDS,
        )
    except OSError as error:
        return str(error)

    details = (
        result["stderr"]
        or result["stdout"]
    )

    if (
        result["exit_code"] == 0
        or "no such container" in details.lower()
    ):
        return None

    return (
        "Container cleanup failed: "
        + clip(details)
    )


def run_in_docker(
    command: list[str],
    working_directory: Path,
    image_name: str = DOCKER_IMAGE,
    timeout: float = COMMAND_TIMEOUT_SECONDS,
    output_limit: int = 32_768,
    read_only: bool = False,
):
    if (
        not isinstance(command, list)
        or not command
        or any(
            not isinstance(argument, str)
            for argument in command
        )
        or not command[0].strip()
    ):
        raise ValueError(
            "Command must be a non-empty list of strings "
            "with a non-empty executable."
        )

    working_directory = Path(
        working_directory
    ).resolve()

    if not working_directory.is_dir():
        raise ValueError(
            "Working directory does not exist: "
            f"{working_directory}"
        )

    container_name = (
        f"evolving-swe-{uuid4().hex}"
    )

    mount = f"{working_directory}:/workspace"

    if read_only:
        mount += ":ro"

    docker_command = [
        "docker",
        "run",
        "--name", container_name,
        "--rm",
        "--memory", "512m",
        "--cpus", "1",
        "--pids-limit", "128",
        "--network", "none",
        "--cap-drop", "ALL",
        "--security-opt", "no-new-privileges:true",
        "--read-only",
        "--tmpfs", "/tmp:rw,noexec,nosuid,size=64m",
        "-v", mount,
        "-w", "/workspace",
        "-e", "GIT_CONFIG_COUNT=1",
        "-e", "GIT_CONFIG_KEY_0=safe.directory",
        "-e", "GIT_CONFIG_VALUE_0=/workspace",
        image_name,
        *command,
    ]

    outcome = None

    try:
        outcome = bounded_process(
            docker_command,
            timeout=timeout,
            limit=output_limit,
        )

    except FileNotFoundError:
        outcome = {
            "exit_code": -1,
            "stdout": "",
            "stderr": (
                "Docker executable was not found."
            ),
        }

    except OSError as error:
        outcome = {
            "exit_code": -1,
            "stdout": "",
            "stderr": (
                f"Failed to run Docker: {error}"
            ),
        }

    finally:
        # Stopping the Docker CLI alone does not guarantee
        # that its container has stopped.
        cleanup_error = _remove_container(
            container_name
        )

        if cleanup_error:
            if outcome is not None:
                outcome["cleanup_failed"] = True
                outcome["exit_code"] = -1

                outcome["stderr"] = (
                    f"{outcome['stderr']}\n"
                    f"{cleanup_error}"
                ).strip()

            else:
                print(
                    cleanup_error,
                    file=sys.stderr,
                )

    return outcome