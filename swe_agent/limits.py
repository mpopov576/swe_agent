from contextlib import contextmanager
import json
import multiprocessing as mp
import os
import signal
import subprocess
import tempfile
import threading
import time
from pathlib import Path


TEXT_LIMIT = 12_000
CONTEXT_LIMIT = 24_000
PROMPT_LIMIT = 64_000
PATCH_LIMIT = 8 * 1024 * 1024
MARKER = "\n[TRUNCATED]\n"


class Incomplete(RuntimeError):
    def __init__(self, status, detail=""):
        self.status = status
        super().__init__(detail or status)


def clip(text, limit=TEXT_LIMIT):
    text = str(text)
    if len(text) <= limit:
        return text

    return (
        text[:max(0, limit - len(MARKER))]
        + MARKER[:limit]
    )


class Deadline:
    def __init__(self, seconds):
        if seconds <= 0:
            raise ValueError("Deadline must be positive")

        self.end = time.monotonic() + seconds

    @contextmanager
    def paused(self):
        started = time.monotonic()
        try:
            yield
        finally:
            self.end += time.monotonic() - started

    def remaining(self, maximum=None):
        seconds = self.end - time.monotonic()

        if seconds <= 0:
            raise Incomplete("deadline_exceeded")

        if maximum is not None:
            return min(seconds, maximum)

        return seconds


def _worker(path, function, args):
    try:
        data = {"value": function(*args)}
    except Exception as error:
        data = {
            "error": clip(f"{type(error).__name__}: {error}"),
            "status": getattr(error, "status", "worker_error"),
        }

    Path(path).write_text(
        json.dumps(data, ensure_ascii=True),
        encoding="utf-8",
    )


def isolated_call(function, args, seconds, deadline, timeout_status):
    timeout = deadline.remaining(seconds)

    with tempfile.TemporaryDirectory(prefix="swe-call-") as directory:
        path = str(Path(directory) / "result.json")

        process = mp.get_context("spawn").Process(
            target=_worker,
            args=(path, function, args),
            daemon=True,
        )

        process.start()

        try:
            process.join(timeout)

            if process.is_alive():
                deadline.remaining()
                raise Incomplete(timeout_status)

            deadline.remaining()

            if process.exitcode != 0 or not Path(path).exists():
                raise Incomplete(
                    "worker_failed",
                    f"Worker exit: {process.exitcode}",
                )

            if Path(path).stat().st_size > 2_000_000:
                raise Incomplete("worker_output_limit")

            data = json.loads(
                Path(path).read_text(encoding="utf-8")
            )

            if "error" in data:
                raise Incomplete(data["status"], data["error"])

            return data["value"]

        finally:
            if process.is_alive():
                process.terminate()
                process.join(1)

            if process.is_alive():
                process.kill()
                process.join(1)

            if not process.is_alive():
                process.close()


def bounded_process(
    command,
    *,
    timeout=60,
    limit=32_768,
    input_text=None,
):

    buffers = [bytearray(), bytearray()]
    truncated = [False, False]
    errors = []

    def drain(pipe, index):
        try:
            while True:
                block = pipe.read(8192)

                if not block:
                    break

                room = max(0, limit - len(buffers[index]))
                buffers[index].extend(block[:room])
                truncated[index] |= len(block) > room

        except Exception as error:
            errors.append(str(error))

        finally:
            pipe.close()

    with tempfile.TemporaryFile() as stdin:
        if input_text is not None:
            stdin.write(input_text.encode("utf-8"))
            stdin.seek(0)

        process = subprocess.Popen(
            command,
            stdin=stdin,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            start_new_session=(os.name == "posix"),
        )

        threads = [
            threading.Thread(
                target=drain,
                args=(pipe, index),
                daemon=True,
            )
            for index, pipe in enumerate(
                (process.stdout, process.stderr)
            )
        ]

        for thread in threads:
            thread.start()

        timed_out = False

        try:
            try:
                process.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                timed_out = True

        finally:
            if os.name == "posix":
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
            elif process.poll() is None:
                process.kill()

            process.wait(timeout=5)

            for thread in threads:
                thread.join(1)

    capture_error = (
        bool(errors)
        or any(thread.is_alive() for thread in threads)
    )

    return {
        "exit_code": (
            -1 if timed_out or capture_error
            else process.returncode
        ),
        "stdout": bytes(buffers[0]).decode(
            "utf-8",
            errors="surrogateescape",
        ),
        "stderr": bytes(buffers[1]).decode(
            "utf-8",
            errors="surrogateescape",
        ),
        "stdout_truncated": truncated[0],
        "stderr_truncated": truncated[1],
        "timed_out": timed_out,
        "capture_error": capture_error,
    }