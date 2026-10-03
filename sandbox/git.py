from pathlib import Path

from swe_agent.limits import bounded_process


def clone_repository(
    repo_url: str,
    destination: Path,
    timeout=120,
):
    destination = Path(destination)

    result = bounded_process(
        [
            "git",
            "clone",
            "--config", "core.autocrlf=false",
            "--config", "core.eol=lf",
            "--",
            repo_url,
            str(destination),
        ],
        timeout=timeout,
    )

    if (
        result.get("exit_code") != 0
        or result.get("timed_out")
        or result.get("capture_error")
    ):
        raise RuntimeError(f"Clone failed: {result}")