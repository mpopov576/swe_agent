import shlex
from pathlib import Path

from swe_agent.limits import bounded_process


BASE_IMAGE = "evolving-swe-sandbox:1.0"
BUILD_TIMEOUT_SECONDS = 600


INSTALL_SCRIPT = """
from pathlib import Path
import subprocess
import sys
import tomllib

root = Path("/workspace")


def install(*arguments):
    subprocess.run(
        [sys.executable, "-m", "pip", "install", *arguments],
        check=True,
    )


for filename in ("requirements.txt", "requirements-dev.txt"):
    path = root / filename

    if path.is_file():
        install("-r", str(path))


has_package = (
    (root / "setup.py").is_file()
    or (root / "setup.cfg").is_file()
)

pyproject = root / "pyproject.toml"

if pyproject.is_file():
    with pyproject.open("rb") as file:
        config = tomllib.load(file)

    has_package = has_package or (
        "build-system" in config
        or "project" in config
    )

if has_package:
    install("-e", str(root))
"""


def build_repository_image(
    repo_path: Path,
    image_name: str,
    timeout=BUILD_TIMEOUT_SECONDS,
):
    repo_path = Path(repo_path).resolve()

    if not repo_path.is_dir():
        raise ValueError(
            f"Repository does not exist: {repo_path}"
        )

    # repr() represents newlines as escapes, keeping the
    # Dockerfile RUN instruction on one physical line.
    install_command = shlex.quote(
        f"exec({INSTALL_SCRIPT!r})"
    )

    dockerfile = (
        f"FROM {BASE_IMAGE}\n"
        "USER root\n"
        "WORKDIR /workspace\n"
        "COPY --chown=sandbox:sandbox . /workspace\n"
        f"RUN python -c {install_command}\n"
        "USER sandbox\n"
    )

    result = bounded_process(
        [
            "docker",
            "build",
            "--tag", image_name,
            "--file", "-",
            str(repo_path),
        ],
        input_text=dockerfile,
        timeout=timeout,
    )

    if result["exit_code"] != 0:
        raise RuntimeError(
            "Repository environment build failed:\n"
            f"{result}"
        )


def remove_repository_image(image_name: str):
    result = bounded_process(
        [
            "docker",
            "image",
            "rm",
            image_name,
        ],
        timeout=30,
    )

    details = (
        result["stderr"]
        or result["stdout"]
    )

    if (
        result["exit_code"] != 0
        and "no such image" not in details.lower()
    ):
        raise RuntimeError(
            f"Could not remove image {image_name}: "
            f"{details}"
        )