import argparse
import csv
import hashlib
import json
import re
import shutil
import stat
import subprocess
import tempfile
import time
from pathlib import Path

from eval_tasks import TASKS
from main import main


ROOT = Path(__file__).resolve().parent
OUTPUT = ROOT / "evaluation-results"
IMAGE = "evolving-swe-sandbox:1.0"

SETTINGS = {
    "agent_model": "qwen3:14b",
    "judge_model": "qwen3:14b",
    "embedding_model": "sentence-transformers/all-MiniLM-L6-v2",
    "total_seconds": 900,
    "request_timeout": 300,
}


def command(arguments, timeout=120):
    result = subprocess.run(
        arguments,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr or result.stdout)
    return result.stdout.strip()


def file_hash(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save_json(path, data):
    path.write_text(
        json.dumps(data, indent=2),
        encoding="utf-8",
    )


def prepare_manifest():
    OUTPUT.mkdir(exist_ok=True)
    manifest_path = OUTPUT / "manifest.json"
    tasks = []

    for task in TASKS:
        repo = ROOT / "eval-repos" / task["name"]
        checker = ROOT / "eval-checks" / task["checker"]

        if not repo.is_dir() or not checker.is_file():
            raise RuntimeError(f"Missing repository or checker: {task['name']}")

        # Check tracked files; incidental untracked caches are not copied.
        changes = command([
            "git", "-C", str(repo),
            "status", "--porcelain", "--untracked-files=no",
        ])
        if changes:
            raise RuntimeError(
                f"Tracked files changed in {repo}. "
                "Restore the original task before evaluating."
            )

        commit = command([
            "git", "-C", str(repo), "rev-parse", "HEAD",
        ])
        tasks.append({
            **task,
            "base_commit": commit,
            "checker_sha256": file_hash(checker),
        })

    manifest = {
        "settings": SETTINGS,
        "image_id": command([
            "docker", "image", "inspect", IMAGE,
            "--format", "{{.Id}}",
        ]),
        "tasks": tasks,
    }

    if manifest_path.exists():
        previous = json.loads(manifest_path.read_text(encoding="utf-8"))
        if previous != manifest:
            raise RuntimeError(
                "Tasks, commits, checkers, image, or settings changed "
                "since this evaluation started."
            )
    else:
        save_json(manifest_path, manifest)

    return tasks


def remove_checkout(path):
    def make_writable_and_retry(function, filename, error):
        Path(filename).chmod(stat.S_IWRITE)
        function(filename)

    shutil.rmtree(path, onerror=make_writable_and_retry)


def fresh_checkout(task, destination):
    source = ROOT / "eval-repos" / task["name"]
    command([
        "git", "clone", "--no-hardlinks", "--no-checkout",
        "--config", "core.autocrlf=false",
        "--config", "core.eol=lf",
        str(source), str(destination),
    ])
    command([
        "git", "-C", str(destination),
        "checkout", "--detach", task["base_commit"],
    ])


def run_checker(repo, checker):
    result = subprocess.run(
        [
            "docker", "run", "--rm",
            "--network", "none",
            "--read-only",
            "--cap-drop", "ALL",
            "--security-opt", "no-new-privileges",
            "--pids-limit", "128",
            "--memory", "512m",
            "--cpus", "1",
            "--tmpfs", "/tmp:rw,noexec,nosuid,size=64m",
            "--mount",
            f"type=bind,source={repo},target=/workspace,readonly",
            "--mount",
            f"type=bind,source={checker},target=/checker.py,readonly",
            "-w", "/workspace",
            IMAGE,
            "python", "-B", "/checker.py", "/workspace",
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=90,
    )

    output = result.stdout + "\n" + result.stderr
    ran_tests = re.search(r"Ran ([1-9]\d*) tests?", output)

    if not ran_tests:
        status = "checker_error"
    elif result.returncode == 0 and re.search(r"^OK\s*$", output, re.MULTILINE):
        status = "passed"
    else:
        status = "failed"

    return {
        "status": status,
        "exit_code": result.returncode,
        "stdout": result.stdout,
        "stderr": result.stderr,
    }


def run_attempt(task, repeat):
    attempt_dir = OUTPUT / f"{task['name']}-{repeat}"
    attempt_dir.mkdir(exist_ok=True)

    row = {
        "task": task["name"],
        "repeat": repeat,
        "agent_status": "",
        "judge_result": "",
        "patch_present": False,
        "independent_result": "not_run",
        "agent_seconds": None,
        "artifact_directory": "",
        "error": "",
    }

    temporary = Path(tempfile.mkdtemp(prefix="manual-evaluation-"))
    repo = temporary / "repo"
    checker = ROOT / "eval-checks" / task["checker"]

    try:
        fresh_checkout(task, repo)

        baseline = run_checker(repo, checker)
        save_json(attempt_dir / "baseline.json", baseline)

        if baseline["status"] != "failed":
            raise RuntimeError(
                "Baseline must run its tests and fail. Inspect baseline.json."
            )

        started = time.perf_counter()
        try:
            result = main(
                repo_url=str(repo),
                issue_text=task["issue"],
                approval_callback=lambda diff, verdict: False,
                **SETTINGS,
            )
        finally:
            row["agent_seconds"] = round(time.perf_counter() - started, 2)

        row["agent_status"] = result.get("status", "")
        row["judge_result"] = (result.get("verdict") or {}).get("result", "")
        row["artifact_directory"] = result.get("artifact_directory", "")
        save_json(attempt_dir / "agent-result.json", result)

        if not result.get("patch_complete"):
            raise RuntimeError("Agent did not capture a complete patch")

        artifact = Path(result["artifact_directory"]) / "result.json"
        saved = json.loads(artifact.read_text(encoding="utf-8"))
        if saved["metadata"].get("base_commit") != task["base_commit"]:
            raise RuntimeError("Agent used the wrong starting commit")

        patch = (result.get("diff") or {}).get("git_diff", "")
        row["patch_present"] = bool(patch.strip())

        if not patch.strip():
            row["independent_result"] = "no_patch"
        else:
            patch_path = attempt_dir / "patch.diff"
            patch_path.write_bytes(patch.encode("utf-8"))

            try:
                command([
                    "git", "-C", str(repo),
                    "apply", "--check", str(patch_path),
                ])
                command([
                    "git", "-C", str(repo),
                    "apply", str(patch_path),
                ])
            except RuntimeError as error:
                row["independent_result"] = "patch_apply_failed"
                row["error"] = str(error)
            else:
                checked = run_checker(repo, checker)
                save_json(attempt_dir / "checks.json", checked)
                row["independent_result"] = checked["status"]

    except Exception as error:
        row["error"] = f"{type(error).__name__}: {error}"

    finally:
        save_json(attempt_dir / "summary.json", row)
        try:
            remove_checkout(temporary)
        except OSError as error:
            print(f"Temporary checkout retained: {temporary}: {error}")

    print(
        f"{task['name']} / attempt {repeat}: "
        f"{row['independent_result']} "
        f"(judge: {row['judge_result'] or 'none'})"
    )
    if row["error"]:
        print(row["error"])

    return row


def write_csv():
    rows = [
        json.loads(path.read_text(encoding="utf-8"))
        for path in sorted(OUTPUT.glob("*/summary.json"))
    ]
    if rows:
        with (OUTPUT / "results.csv").open(
            "w", newline="", encoding="utf-8"
        ) as stream:
            writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)


def run_suite(limit):
    tasks = prepare_manifest()
    completed_now = 0

    for task in tasks:
        for repeat in range(1, 4):
            summary = OUTPUT / f"{task['name']}-{repeat}" / "summary.json"
            if summary.exists():
                continue

            row = run_attempt(task, repeat)
            write_csv()
            completed_now += 1

            # Stop on a scoring/setup problem instead of wasting more runs.
            if row["independent_result"] in ("not_run", "checker_error"):
                print("Stopped: inspect this attempt before continuing.")
                return

            if limit and completed_now >= limit:
                return

    print("All 18 attempts recorded.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--limit",
        type=int,
        default=1,
        help="Number of new attempts; 0 runs all remaining attempts.",
    )
    args = parser.parse_args()
    run_suite(args.limit)