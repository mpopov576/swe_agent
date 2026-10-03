import json

from swe_agent.judge_agent import JudgeAgent
from swe_agent.tool_manager import ToolManager


class FakeLLMClient:
    def __init__(self, messages):
        self.messages = messages
        self.position = 0

    def chat(self, messages, tools=None):
        if self.position >= len(self.messages):
            raise AssertionError(
                "The judge requested an unexpected extra response."
            )

        message = self.messages[self.position]
        self.position += 1

        return {"message": message}


def command_message():
    return {
        "role": "assistant",
        "content": "",
        "tool_calls": [
            {
                "function": {
                    "name": "run_command_in_sandbox",
                    "arguments": {
                        "command": ["python", "check_fix.py"],
                    },
                }
            }
        ],
    }


def passing_message(execution_id=None, summary=None):
    verdict = {
        "result": "pass",
        "failed_checks": [],
    }

    if execution_id is not None:
        verdict["verification_execution_id"] = execution_id

    if summary is not None:
        verdict["verification_summary"] = summary

    return {
        "role": "assistant",
        "content": (
            "<reasoning>The fix appears correct.</reasoning>\n"
            f"<verdict>{json.dumps(verdict)}</verdict>"
        ),
    }


def run_judge(messages, command_results):
    executed_commands = []

    def fake_run_command(command):
        result_index = len(executed_commands)
        executed_commands.append(list(command))

        if result_index >= len(command_results):
            return {
                "exit_code": -1,
                "stdout": "",
                "stderr": "Unexpected extra command",
            }

        return command_results[result_index]

    tool_manager = ToolManager()
    tool_manager.register_tool(
        name="run_command_in_sandbox",
        handler=fake_run_command,
        description="Fake command execution for this test",
        permission="execute",
        parameters={
            "type": "object",
            "properties": {
                "command": {
                    "type": "array",
                    "items": {"type": "string"},
                }
            },
            "required": ["command"],
        },
    )

    judge = JudgeAgent(
        llm_client=FakeLLMClient(messages),
        tool_manager=tool_manager,
    )

    verdict = judge.evaluate(
        issue_text="Fix the incorrect calculation.",
        diff={
            "changed_files": " M calculation.py",
            "git_diff": "Example patch for testing",
        },
    )

    return verdict, executed_commands


def command_result(exit_code):
    return {
        "exit_code": exit_code,
        "stdout": "Simulated check output",
        "stderr": "",
    }


def assert_verification_rejected(verdict):
    assert verdict["result"] == "fail"
    assert "verification_incomplete" in verdict["failed_checks"]


def test_pass_without_execution_is_rejected():
    verdict, commands = run_judge(
        messages=[passing_message()],
        command_results=[],
    )

    assert_verification_rejected(verdict)
    assert commands == []
    assert verdict["executions"] == {}


def test_invented_execution_id_is_rejected():
    verdict, commands = run_judge(
        messages=[
            command_message(),
            passing_message(
                execution_id="exec_999",
                summary="The regression check passed.",
            ),
        ],
        command_results=[command_result(0)],
    )

    assert_verification_rejected(verdict)
    assert len(commands) == 1
    assert "exec_1" in verdict["executions"]
    assert "exec_999" not in verdict["executions"]


def test_failed_execution_is_rejected():
    verdict, commands = run_judge(
        messages=[
            command_message(),
            passing_message(
                execution_id="exec_1",
                summary="The regression check passed.",
            ),
        ],
        command_results=[command_result(1)],
    )

    assert_verification_rejected(verdict)
    assert len(commands) == 1

    recorded = verdict["executions"]["exec_1"]["result"]
    assert recorded["exit_code"] == 1


def test_success_without_explanation_is_rejected():
    verdict, commands = run_judge(
        messages=[
            command_message(),
            passing_message(execution_id="exec_1"),
        ],
        command_results=[command_result(0)],
    )

    assert_verification_rejected(verdict)
    assert len(commands) == 1


def test_success_with_explanation_is_accepted():
    verdict, commands = run_judge(
        messages=[
            command_message(),
            passing_message(
                execution_id="exec_1",
                summary="The check exercised the reported failing input.",
            ),
        ],
        command_results=[command_result(0)],
    )

    assert verdict["result"] == "pass"
    assert verdict["failed_checks"] == []
    assert commands == [["python", "check_fix.py"]]

    recorded = verdict["executions"]["exec_1"]

    assert recorded["command"] == ["python", "check_fix.py"]
    assert recorded["result"]["exit_code"] == 0

    tool_messages = [
        message
        for message in verdict["messages"]
        if message["role"] == "tool"
    ]

    assert len(tool_messages) == 1

    tool_output = json.loads(tool_messages[0]["content"])
    assert tool_output["execution_id"] == "exec_1"


def test_successful_retry_can_support_pass():
    verdict, commands = run_judge(
        messages=[
            command_message(),
            command_message(),
            passing_message(
                execution_id="exec_2",
                summary="The second verification execution succeeded.",
            ),
        ],
        command_results=[
            command_result(1),
            command_result(0),
        ],
    )

    assert verdict["result"] == "pass"
    assert len(commands) == 2
    assert verdict["executions"]["exec_1"]["result"]["exit_code"] == 1
    assert verdict["executions"]["exec_2"]["result"]["exit_code"] == 0


