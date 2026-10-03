import os
import stat
import shutil
from pathlib import Path
from tempfile import mkdtemp
from uuid import uuid4

from swe_agent.limits import Incomplete, PATCH_LIMIT
from sandbox.git import clone_repository
from sandbox.docker_executor import (
    DOCKER_IMAGE,
    run_in_docker,
)
from sandbox.environment import (
    build_repository_image,
    remove_repository_image,
)


class SandboxCommandError(RuntimeError):
    def __init__(self, command, result):
        self.command = list(command)
        self.result = result

        details = (
            result.get("stderr")
            or result.get("stdout")
            or "No output was provided."
        ).strip()

        super().__init__(
            f"Command failed: {self.command!r}\n"
            f"Exit code: {result.get('exit_code')}\n"
            f"{details}"
        )


class SandboxRunner:
    def __init__(
        self,
        repo_url: str,
        deadline=None,
    ):
        self.deadline = deadline
        self.cleanup_failed = False
        self.base_commit = None
        self.repo_url = repo_url
        self.repo_path = None
        self.image_name = DOCKER_IMAGE
        self._repository_image = None

    def clone_repo(self):
        temp_dir = mkdtemp()
        self.repo_path = Path(temp_dir) / "repo"

        clone_repository(
            self.repo_url,
            self.repo_path,
            timeout=self._timeout(120),
        )

    def prepare_environment(self):
        if self.repo_path is None:
            raise RuntimeError(
                "Clone the repository first."
            )

        if self._repository_image is not None:
            raise RuntimeError(
                "A repository environment has "
                "already been requested."
            )

        image_name = (
            f"evolving-swe-task:{uuid4().hex}"
        )

        self._repository_image = image_name

        build_repository_image(
            self.repo_path,
            image_name,
            timeout=self._timeout(600),
        )

        self.image_name = image_name

    def _timeout(self, maximum):
        if self.deadline:
            return self.deadline.remaining(maximum)

        return maximum

    def run_command_in_sandbox(
        self,
        command,
        *,
        read_only=False,
        output_limit=32_768,
    ):
        if self.cleanup_failed:
            raise Incomplete(
                "cleanup_failed",
                "A container may still be writing; "
                "workspace preserved",
            )

        result = run_in_docker(
            command,
            self.repo_path,
            image_name=self.image_name,
            timeout=self._timeout(60),
            output_limit=output_limit,
            read_only=read_only,
        )

        if result.get("cleanup_failed"):
            self.cleanup_failed = True

            raise Incomplete(
                "cleanup_failed",
                result["stderr"],
            )

        if self.deadline:
            self.deadline.remaining()

        return result

    def run_checked(
        self,
        command,
        *,
        output_limit=32_768,
    ):
        result = self.run_command_in_sandbox(
            command,
            output_limit=output_limit,
        )

        if (
            result.get("exit_code") != 0
            or result.get("stdout_truncated")
            or result.get("stderr_truncated")
            or result.get("capture_error")
        ):
            raise SandboxCommandError(
                command,
                result,
            )

        return result

    def get_diff(self):
        self.run_checked([
            "git",
            "add",
            "-A",
        ])

        # Keep comparing against the original commit,
        # including after an approved commit is created.
        base = (
            [self.base_commit]
            if self.base_commit
            else []
        )

        common = [
            "git",
            "diff",
            "--cached",
            "--no-color",
            "--no-ext-diff",
            "--no-textconv",
        ]

        names = self.run_checked(
            common + [
                "--name-status",
                *base,
            ],
            output_limit=PATCH_LIMIT,
        )

        patch = self.run_checked(
            common + [
                "--binary",
                "--full-index",
                *base,
            ],
            output_limit=PATCH_LIMIT,
        )

        return {
            "changed_files": names["stdout"],
            "git_diff": patch["stdout"],
        }

    def delete_environment(self):
        if self._repository_image is None:
            return

        remove_repository_image(
            self._repository_image
        )

        self._repository_image = None
        self.image_name = DOCKER_IMAGE

    def delete_dir(self):
        def remove_readonly(func, path, exc_info):
            os.chmod(path, stat.S_IWRITE)
            func(path)

        shutil.rmtree(
            self.repo_path.parent,
            onerror=remove_readonly,
        )