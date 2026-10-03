from swe_agent.limits import Incomplete, CONTEXT_LIMIT, clip
from swe_agent.llm_client import tool_text


SYSTEM_PROMPT = """You fix repository issues using the available tools.
The repository root is '.' for file tools and the command working directory.
Start with the supplied root listing. Do not invent a 'repo/' subdirectory.
Context may show absolute host paths; use paths relative to the root for tools.
list_dir lists filenames; search_dir searches file CONTENTS, not filenames.

Trace the reported behavior into its dependencies and fix its actual cause.
Read current code before editing it.
edit_file replaces one exact old_text match with new_text, not a line range.
Copy old_text exactly, including indentation. Include surrounding code if the
text occurs more than once. Make small edits, then read the file to confirm them.
If an edit is rejected, read the file again before retrying.
Discover the language and test framework from actual files and documentation.
Run relevant existing tests with their runner, or a focused reproducer that
checks expected behavior and fails if it is wrong. Merely loading a test file,
printing a value, or running zero tests does not verify a fix.
If a command fails, inspect the error and root listing before changing files.
Do not create directories or package files just to satisfy an invented path.
Do not weaken tests, make unrelated changes, or change Git history.
After your final edit, execute verification. Report actual results and any
missing runtime or dependencies honestly. Use tool calls to act, not prose.
Your final summary requests independent review; it does not approve the fix.
"""


class SWEAgent:
    def __init__(
        self,
        llm_client,
        tool_manager,
        context_manager=None,
        max_iterations=15,
    ):
        self.llm_client = llm_client
        self.tool_manager = tool_manager
        self.context_manager = context_manager
        self.max_iterations = max_iterations

    def run(self, issue_text: str, feedback: str = None):
        self.messages = []
        self.iterations = 0

        try:
            return self._run(issue_text, feedback)
        except Incomplete as error:
            return self._result(error.status, error=str(error))

    def _result(self, status, **fields):
        return {
            "status": status,
            "iterations": self.iterations,
            "messages": self.messages,
            **fields,
        }

    def _execute(self, name, arguments):
        try:
            return self.tool_manager.execute_tool(name, **arguments)
        except Incomplete:
            raise
        except Exception as error:
            return {"error": clip(str(error))}

    def _run(self, issue_text, feedback):
        root_listing = self._execute("list_dir", {"directory": "."})
        context = ""

        if self.context_manager is not None:
            context = self.context_manager.retrieve(issue_text)

        self.messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": (
                    f"Issue:\n{issue_text}\n\n"
                    f"Repository root '.' contains:\n"
                    f"{tool_text(root_listing)}\n\n"
                    f"Relevant code:\n{clip(context, CONTEXT_LIMIT)}"
                ),
            },
        ]

        if feedback:
            self.messages.append({
                "role": "user",
                "content": (
                    "Previous attempt needs correction:\n"
                    + clip(feedback, 8000)
                ),
            })

        commands_since_edit = []
        tool_schemas = self.tool_manager.get_tool_schemas()

        for self.iterations in range(1, self.max_iterations + 1):
            response = self.llm_client.chat(
                self.messages,
                tools=tool_schemas,
            )
            message = response["message"]
            self.messages.append(message)
            tool_calls = message.get("tool_calls") or []

            if not tool_calls:
                # "done" means ready for review, not that the fix is approved.
                if commands_since_edit:
                    return self._result(
                        "done",
                        summary=message.get("content", ""),
                    )

                self.messages.append({
                    "role": "user",
                    "content": (
                        "No verification command has executed since the last edit. "
                        "Use tools now. Root is '.', as listed above. If verification "
                        "is unavailable, run the relevant command to capture the error."
                    ),
                })
                continue

            for call in tool_calls:
                name = call["function"]["name"]
                arguments = call["function"]["arguments"]

                if name in ("edit_file", "create_file"):
                    commands_since_edit.clear()

                output = self._execute(name, arguments)

                if name == "run_command_in_sandbox":
                    commands_since_edit.append(output)

                self.messages.append({
                    "role": "tool",
                    "tool_name": name,
                    "content": tool_text(output),
                })

        return self._result("max_iterations_reached")