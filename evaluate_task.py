import argparse
import json
import subprocess
from pathlib import Path
from tempfile import TemporaryDirectory

from main import main


def git(*arguments):
    result = subprocess.run(
        ["git", *arguments],
        capture_output=True,
        text=True,
        timeout=600,
    )

    if result.returncode != 0:
        raise RuntimeError(result.stderr or result.stdout)

    return result.stdout.strip()


def run_task(task_path):
    task = json.loads(
        Path(task_path).read_text(encoding="utf-8")
    )

    # Prepare a separate checkout at the benchmark's exact starting commit.
    with TemporaryDirectory(prefix="swe-bench-input-") as directory:
        repo = Path(directory) / "repo"

        git(
            "clone",
            "--no-checkout",
            "--config", "core.autocrlf=false",
            f"https://github.com/{task['repo']}.git",
            str(repo),
        )

        git(
            "-C", str(repo),
            "checkout",
            "-b", "benchmark-base",
            task["base_commit"],
        )

        actual_commit = git("-C", str(repo), "rev-parse", "HEAD")
        if actual_commit != task["base_commit"]:
            raise RuntimeError("Starting commit does not match the benchmark")

        print(f"Task: {task['instance_id']}")
        print(f"Starting commit: {actual_commit}")
        print("If asked to approve, enter n. The saved patch will be evaluated.")

        result = main(
            repo_url=str(repo),
            issue_text=task["problem_statement"],
            agent_model="qwen3:14b",
            judge_model="qwen3:14b",
            embedding_model="sentence-transformers/all-MiniLM-L6-v2",
            total_seconds=900,
            request_timeout=300,
        )

    artifact_directory = Path(result["artifact_directory"])

    # Confirm the agent actually worked from the expected commit.
    saved = json.loads(
        (artifact_directory / "result.json").read_text(encoding="utf-8")
    )
    recorded_commit = saved["metadata"].get("base_commit")

    if recorded_commit != task["base_commit"]:
        raise RuntimeError(
            "The run did not establish the required starting commit. "
            f"Inspect {artifact_directory / 'result.json'}"
        )

    diff = result.get("diff") or {}
    patch = diff.get("git_diff", "")

    if not result.get("patch_complete"):
        raise RuntimeError(
            "Patch capture was incomplete. "
            f"Inspect {artifact_directory / 'result.json'}"
        )

    prediction = {
        "instance_id": task["instance_id"],
        "model_name_or_path": "evolving-swe-qwen3-14b",
        "model_patch": patch,
    }

    predictions_path = artifact_directory / "predictions.jsonl"
    predictions_path.write_text(
        json.dumps(prediction) + "\n",
        encoding="utf-8",
    )

    (artifact_directory / "benchmark-task.json").write_text(
        json.dumps(task, indent=2),
        encoding="utf-8",
    )

    print(f"\nAgent status: {result['status']}")
    print(f"Prediction saved to: {predictions_path}")

    if not patch.strip():
        print("No patch was produced; retain this as an unsuccessful attempt.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("task_file")
    args = parser.parse_args()
    run_task(args.task_file)