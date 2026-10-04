from pathlib import Path
import sys

from swe_agent.limits import Deadline, Incomplete, clip, isolated_call
from swe_agent.llm_client import LLMClient
from swe_agent.tool_manager import ToolManager
from swe_agent.tools.sandboxed import make_sandboxed_tools
from swe_agent.tools.schemas import TOOL_SCHEMAS
from swe_agent.swe_agent import SWEAgent
from swe_agent.judge_agent import JudgeAgent
from swe_agent.verification_loop import VerificationLoop
from swe_agent.run_artifacts import save_run_result
from swe_agent.context.context_manager import RepositoryContext
from sandbox.runner import SandboxRunner
from swe_agent.verification import verify_fix


def cleanup_safely(description, action):
    try:
        action()
    except Exception as error:
        print(f"Cleanup warning — {description}: {error}", file=sys.stderr)


def _unload_model(model):
    import os

    backend = os.environ.get(
        "SWE_LLM_BACKEND",
        "ollama",
    ).strip().lower()

    if backend == "bedrock":
        return None

    from ollama import Client

    Client(timeout=10).chat(
        model=model,
        messages=[],
        keep_alive=0,
    )

    return None


def build_agent_tool_manager(sandbox: SandboxRunner) -> ToolManager:
    tool_manager = ToolManager()

    sandboxed = make_sandboxed_tools(sandbox.repo_path)

    for name, handler in sandboxed.items():
        tool_manager.register_tool(
            name=name,
            handler=handler,
            description=f"{name} (confined to the sandboxed repo)",
            permission="write",
            parameters=TOOL_SCHEMAS[name],
        )

    tool_manager.register_tool(
        name="run_command_in_sandbox",
        handler=sandbox.run_command_in_sandbox,
        description=(
            "Run a command inside the sandboxed repo "
            "(Docker-isolated)"
        ),
        permission="execute",
        parameters=TOOL_SCHEMAS["run_command_in_sandbox"],
    )

    return tool_manager


def build_judge_tool_manager(sandbox: SandboxRunner) -> ToolManager:
    tool_manager = ToolManager()

    tool_manager.register_tool(
        name="run_command_in_sandbox",
        handler=lambda command: sandbox.run_command_in_sandbox(command, read_only=True),
        description=(
            "Run a command inside the sandboxed repo "
            "(Docker-isolated)"
        ),
        permission="execute",
        parameters=TOOL_SCHEMAS["run_command_in_sandbox"],
    )

    tool_manager.register_tool(
        name="verify_fix",
        handler=lambda command: verify_fix(sandbox, command),
        description=(
            "Run the same command in Docker on the original commit and "
            "the patched repository. The command may use any language."
        ),
        permission="execute",
        parameters=TOOL_SCHEMAS["verify_fix"],
    )

    return tool_manager

def main(
    repo_url,
    issue_text,
    agent_model,
    judge_model,
    embedding_model,
    total_seconds=900,
    request_timeout=120,
    approval_callback=None,
):
    if not issue_text.strip() or len(issue_text) > 8_000:
        raise ValueError("Issue must contain 1–8,000 characters")
    deadline = Deadline(total_seconds)
    sandbox = SandboxRunner(repo_url, deadline=deadline)
    result = None
    saved = False
    models_used = False
    try:
        try:
            sandbox.clone_repo()
            sandbox.prepare_environment()
            sandbox.base_commit = sandbox.run_checked(
                ["git", "rev-parse", "HEAD"]
            )["stdout"].strip()
            context = RepositoryContext(sandbox.repo_path, embedding_model, deadline)
            models_used = True
            loop = VerificationLoop(
                swe_agent=SWEAgent(
                    LLMClient(agent_model, deadline, request_timeout),
                    build_agent_tool_manager(sandbox), context,
                ),
                judge_agent=JudgeAgent(
                    LLMClient(judge_model, deadline, request_timeout),
                    build_judge_tool_manager(sandbox),
                ),
                sandbox=sandbox, deadline=deadline, approval_callback=approval_callback
            )
            result = loop.run(issue_text)
        except Exception as error:
            try:
                deadline.remaining()
            except Incomplete as expired:
                error = expired
            status = error.status if isinstance(error, Incomplete) else "setup_error"
            result = {"status": status, "error": clip(str(error)),
                      "diff": None, "patch_complete": False}
            sandbox.deadline = Deadline(90)
            if sandbox.repo_path and (sandbox.repo_path / ".git").is_dir():
                try:
                    result["diff"] = sandbox.get_diff()
                    result["patch_complete"] = True
                except Exception as capture_error:
                    result["patch_error"] = clip(str(capture_error))

        result["workspace"] = str(sandbox.repo_path) if sandbox.repo_path else None
        directory = save_run_result(
            result,
            {"repo_url": repo_url, "base_commit": sandbox.base_commit,
             "issue_text": issue_text, "agent_model": agent_model,
             "judge_model": judge_model, "embedding_model": embedding_model},
            Path.cwd() / "runs",
        )
        saved = True
        result["artifact_directory"] = str(directory)
        print(f"Run files saved to: {directory}")
        return result
    finally:
        cleanup_safely("removing repository image", sandbox.delete_environment)
        if models_used:
            for model in dict.fromkeys([agent_model, judge_model]):
                cleanup_safely(
                    f"unloading {model}",
                    lambda model=model: isolated_call(
                        _unload_model, (model,), 10, Deadline(12), "cleanup_timeout",
                    ),
                )
        if sandbox.repo_path is not None:
            if saved and result and result.get("patch_complete"):
                cleanup_safely("deleting temporary repository", sandbox.delete_dir)
            else:
                print(f"Workspace preserved at: {sandbox.repo_path.parent}", file=sys.stderr)


