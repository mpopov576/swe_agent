from swe_agent.limits import Incomplete
from swe_agent.llm_client import tool_text
from swe_agent.verification import shows_improvement

import json
import re


class JudgeAgent:
    def __init__(self, llm_client, tool_manager, max_iterations=20):
        self.llm_client = llm_client
        self.tool_manager = tool_manager
        self.max_iterations = max_iterations

    def evaluate(self, issue_text: str, diff: dict):
        if len(diff["git_diff"]) > 24_000 or len(diff["changed_files"]) > 4_000:
            return {"result": "incomplete", "reasoning": "Patch exceeds the judge context budget",
                    "failed_checks": ["diff_context_limit"]}
        system_prompt = (
            "You are a code reviewer judging a proposed fix.\n"
            "Inspect the repository to discover how to test it. "
            "Choose a language-appropriate command and call verify_fix. "
            "The verify_fix tool runs that same command on the original commit "
            "and the patched repository.\n\n"

            "Check that:\n"
            "1. The check exercises the reported issue.\n"
            "2. The original version fails for the reported reason.\n"
            "3. The patched version passes the same check.\n"
            "4. The patch introduces no obvious regressions.\n"
            "5. No unrelated changes were introduced.\n\n"

            "Use the repository's actual test runner when suitable tests exist. "
            "Run the real test files, not a file directly if that only defines tests. "
            "Confirm that tests were collected and executed.\n\n"

            "If suitable tests do not exist, create a focused reproducer inside "
            "the command itself. Use assertions or equivalent checks that exit "
            "nonzero when expected behavior is wrong.\n\n"

            "Do not use print-only checks. A command that prints different values "
            "but exits zero on both versions does not prove the fix. "
            "Listing files, reading code, importing modules, compiling code, "
            "or running zero or skipped tests is not verification.\n\n"

            "Do not modify repository files or Git history. "
            "Use /tmp for temporary verification files and caches. "
            "Each command runs in a fresh Docker container.\n\n"

            "A passing verdict must reference a verify_fix execution where "
            "the original fails and the patched version passes. "
            "Inspect the actual output from both versions. "
            "Do not trust the SWE agent's claims.\n\n"

            "If the patch is demonstrably broken, return 'fail'. "
            "If the runtime is unavailable or the comparison is inconclusive, "
            "return 'incomplete'.\n\n"
            
            "The original must fail because the reported behavior is wrong. "
            "A missing test file, missing dependency, unavailable command, "
            "or zero tests executed is not evidence of the bug.\n"
            "Tests added by the patch do not exist in the original checkout. "
            "For those tests, use a self-contained verification command that "
            "creates and executes the same checks on both versions, using /tmp "
            "if a temporary file is needed. Do not copy patched implementation "
            "code into the original checkout.\n"
            "If verification fails for a setup reason, correct the command "
            "and call verify_fix again before returning your verdict.\n\n"

            "Write your explanation inside "
            "<reasoning></reasoning> tags.\n"
            "Then return exactly one JSON object inside "
            "<verdict></verdict> tags with these fields:\n"
            "- result: 'pass', 'fail', or 'incomplete'\n"
            "- failed_checks: [] for pass, otherwise a list of reasons\n"
            "- verification_execution_id: the verify_fix execution ID for pass, "
            "or null otherwise\n"
            "- verification_summary: what was checked and what the original "
            "and patched results establish\n"
            "- verification_output: an exact nonempty excerpt from the patched "
            "command's stdout or stderr\n"
        )

        messages = [
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": (
                    f"Issue:\n{issue_text}\n\n"
                    f"Changed files:\n{diff['changed_files']}\n\n"
                    f"Diff:\n{diff['git_diff']}"
                ),
            },
        ]

        executions = {}
        verification_retries = 0
        tool_schemas = self.tool_manager.get_tool_schemas()

        for _ in range(self.max_iterations):
            response = self.llm_client.chat(
                messages,
                tools=tool_schemas,
            )

            message = response["message"]
            messages.append(message)

            tool_calls = message.get("tool_calls")

            if not tool_calls:
                verdict = self._parse_verdict(
                    message.get("content", "")
                )
                verdict = self._check_verification_evidence(
                    verdict,
                    executions,
                )

                checks = verdict.get("failed_checks", [])
                retryable = any(
                    check in (
                        "verification_incomplete",
                        "invalid_judge_response",
                    )
                    for check in checks
                )

                if retryable:
                    if verification_retries < 2:
                        verification_retries += 1
                        messages.append({
                            "role": "user",
                            "content": (
                                    "Your review needs correction:\n"
                                    + verdict.get("reasoning", "")
                                    + "\nIf verification is inadequate, call "
                                      "verify_fix with a self-contained check that "
                                      "runs on both versions. The original must "
                                      "fail because of the reported bug, not a "
                                      "missing file or dependency. If only your "
                                      "response format is wrong, return one complete "
                                      "<verdict>...</verdict> block. Do not modify "
                                      "the repository."
                            ),
                        })
                        continue

                    verdict["result"] = "incomplete"

                verdict["messages"] = messages
                verdict["executions"] = executions
                return verdict

            for call in tool_calls:
                name = call["function"]["name"]
                arguments = call["function"]["arguments"]

                try:
                    result = self.tool_manager.execute_tool(
                        name,
                        **arguments,
                    )
                except Incomplete:
                    raise
                except Exception as error:
                    result = {"error": str(error)}

                if name in ("run_command_in_sandbox", "verify_fix"):
                    execution_id = f"exec_{len(executions) + 1}"

                    record = {
                        "tool": name,
                        "command": arguments.get("command"),
                        "result": result,
                    }

                    executions[execution_id] = record

                    tool_output = {
                        "execution_id": execution_id,
                        **record,
                    }
                else:
                    tool_output = result

                messages.append({
                    "role": "tool",
                    "tool_name": name,
                    "content": tool_text(tool_output),
                })

        return {
            "result": "incomplete",
            "reasoning": (
                "Judge did not reach a verdict within "
                "the iteration limit."
            ),
            "failed_checks": ["max_iterations_reached"],
            "messages": messages,
            "executions": executions,
        }

    def _check_verification_evidence(self, verdict, executions):
        if verdict.get("result") != "pass":
            return verdict

        execution_id = verdict.get("verification_execution_id")
        summary = verdict.get("verification_summary")

        problem = None

        if not isinstance(execution_id, str):
            problem = "No verification execution ID was provided."

        elif execution_id not in executions:
            problem = (
                "The referenced verification command "
                "was not executed."
            )

        elif not isinstance(summary, str) or not summary.strip():
            problem = (
                "The judge did not explain what its "
                "verification checked."
            )

        else:
            record = executions[execution_id]
            if record.get("tool") != "verify_fix":
                problem = "A pass must cite verify_fix, not one patched run."
            elif not shows_improvement(record.get("result")):
                problem = (
                    "The command did not fail on the original and pass "
                    "on the patched repository."
                )

        if problem is not None:
            return {
                "result": "fail",
                "reasoning": (
                    f"Verification incomplete: {problem}\n"
                    f"Judge reasoning: "
                    f"{verdict.get('reasoning', '')}"
                ),
                "failed_checks": ["verification_incomplete"],
            }

        return verdict

    def _parse_verdict(self, content: str):
        def invalid_verdict(problem):
            return {
                "result": "fail",
                "reasoning": f"Invalid judge response: {problem}",
                "failed_checks": ["invalid_judge_response"],
            }

        if not isinstance(content, str):
            return invalid_verdict("Expected a text response.")

        reasoning_match = re.search(
            r"<reasoning>(.*?)</reasoning>",
            content,
            re.DOTALL,
        )

        reasoning = (
            reasoning_match.group(1).strip()
            if reasoning_match
            else ""
        )

        verdict_blocks = re.findall(
            r"<verdict>(.*?)</verdict>",
            content,
            re.DOTALL,
        )

        if len(verdict_blocks) != 1:
            return invalid_verdict(
                "Expected exactly one <verdict> block."
            )

        try:
            verdict = json.loads(verdict_blocks[0].strip())
        except json.JSONDecodeError:
            return invalid_verdict(
                "The verdict block is not valid JSON."
            )

        if not isinstance(verdict, dict):
            return invalid_verdict(
                "The verdict must be a JSON object."
            )

        result = verdict.get("result")

        if result not in ("pass", "fail", "incomplete"):
            return invalid_verdict(
                "'result' must be 'pass', 'fail', or 'incomplete'."
            )

        failed_checks = verdict.get("failed_checks")

        if not isinstance(failed_checks, list):
            return invalid_verdict(
                "'failed_checks' must be a list."
            )

        if any(
                not isinstance(check, str) or not check.strip()
                for check in failed_checks
        ):
            return invalid_verdict(
                "Each failed check must be a non-empty string."
            )

        if result == "pass" and failed_checks:
            return invalid_verdict(
                "A passing verdict cannot contain failed checks."
            )

        if result in ("fail", "incomplete") and not failed_checks:
            return invalid_verdict(
                "A failing verdict must identify a failed check."
            )

        return {
            "result": result,
            "reasoning": reasoning or (
                "Judge accepted the change."
                if result == "pass"
                else "Failed checks: " + "; ".join(failed_checks)
            ),
            "failed_checks": failed_checks,
            "verification_execution_id": verdict.get(
                "verification_execution_id"
            ),
            "verification_summary": verdict.get(
                "verification_summary"
            ),
            "verification_output": verdict.get(
                "verification_output"
            ),
        }