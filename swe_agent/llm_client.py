import json
import os

from swe_agent.limits import (
    Deadline,
    Incomplete,
    PROMPT_LIMIT,
    TEXT_LIMIT,
    clip,
    isolated_call,
)


SUPPORTED_BACKENDS = {"ollama", "bedrock"}


def _chat_ollama(model, messages, tools, timeout):
    from ollama import Client
    import httpx

    try:
        response = Client(timeout=timeout).chat(
            model=model,
            messages=messages,
            tools=tools,
            think=False,
            options={
                "num_predict": 2048,
                "num_ctx": 32768,
            },
            keep_alive="5m",
        )
    except httpx.TimeoutException as error:
        raise Incomplete(
            "model_timeout",
            str(error),
        ) from error

    return response.model_dump(
        mode="json",
        exclude_none=True,
    )


def _bedrock_tool_config(tools):
    if not tools:
        return None

    converted = []

    for tool in tools:
        function = tool["function"]

        parameters = function.get("parameters") or {
            "type": "object",
            "properties": {},
        }

        # Keep the JSON-schema subset expected by Bedrock tool specs.
        schema = {
            key: parameters[key]
            for key in ("type", "properties", "required")
            if key in parameters
        }

        schema.setdefault("type", "object")
        schema.setdefault("properties", {})

        spec = {
            "name": function["name"],
            "inputSchema": {
                "json": schema,
            },
        }

        description = function.get("description")

        if description:
            spec["description"] = description

        converted.append({
            "toolSpec": spec,
        })

    return {
        "tools": converted,
    }


def _bedrock_messages(messages):
    system = []
    converted = []
    pending_tools = []

    index = 0

    while index < len(messages):
        message = messages[index]
        role = message.get("role")

        if role == "system":
            content = message.get("content", "")

            if content:
                system.append({
                    "text": str(content),
                })

            index += 1
            continue

        if role == "user":
            converted.append({
                "role": "user",
                "content": [{
                    "text": str(message.get("content", "")),
                }],
            })

            index += 1
            continue

        if role == "assistant":
            blocks = []
            content = message.get("content", "")

            if content:
                blocks.append({
                    "text": str(content),
                })

            pending_tools = []

            for position, call in enumerate(
                message.get("tool_calls") or []
            ):
                function = call["function"]

                tool_id = (
                    call.get("id")
                    or f"tool_{index}_{position}"
                )

                blocks.append({
                    "toolUse": {
                        "toolUseId": tool_id,
                        "name": function["name"],
                        "input": (
                            function.get("arguments") or {}
                        ),
                    }
                })

                pending_tools.append({
                    "id": tool_id,
                    "name": function["name"],
                })

            if not blocks:
                blocks.append({
                    "text": " ",
                })

            converted.append({
                "role": "assistant",
                "content": blocks,
            })

            index += 1
            continue

        if role == "tool":
            results = []

            while (
                index < len(messages)
                and messages[index].get("role") == "tool"
            ):
                tool_message = messages[index]
                tool_name = tool_message.get("tool_name")

                matching_index = next(
                    (
                        position
                        for position, pending
                        in enumerate(pending_tools)
                        if pending["name"] == tool_name
                    ),
                    None,
                )

                if matching_index is None:
                    if not pending_tools:
                        raise Incomplete(
                            "invalid_tool_history",
                            "Tool result has no matching "
                            "model tool request",
                        )

                    matching_index = 0

                pending = pending_tools.pop(
                    matching_index
                )

                results.append({
                    "toolResult": {
                        "toolUseId": pending["id"],
                        "content": [{
                            "text": str(
                                tool_message.get(
                                    "content",
                                    "",
                                )
                            ),
                        }],
                        "status": "success",
                    }
                })

                index += 1

            converted.append({
                "role": "user",
                "content": results,
            })

            continue

        raise Incomplete(
            "invalid_message_role",
            f"Unsupported message role: {role}",
        )

    return system, converted


def _chat_bedrock(model, messages, tools, timeout):
    import boto3

    from botocore.config import Config
    from botocore.exceptions import (
        BotoCoreError,
        ClientError,
    )

    system, bedrock_messages = _bedrock_messages(
        messages
    )

    request = {
        "modelId": model,
        "messages": bedrock_messages,
        "inferenceConfig": {
            "maxTokens": 2048,
            "temperature": 0,
        },
    }

    if system:
        request["system"] = system

    tool_config = _bedrock_tool_config(tools)

    if tool_config is not None:
        request["toolConfig"] = tool_config

    try:
        client = boto3.client(
            "bedrock-runtime",
            region_name=os.environ.get(
                "AWS_REGION",
                "eu-north-1",
            ),
            config=Config(
                connect_timeout=10,
                read_timeout=timeout,
                retries={
                    "max_attempts": 2,
                    "mode": "standard",
                },
            ),
        )

        response = client.converse(
            **request
        )

    except (BotoCoreError, ClientError) as error:
        raise Incomplete(
            "model_error",
            str(error),
        ) from error

    text_parts = []
    tool_calls = []

    for block in (
        response["output"]["message"]
        .get("content", [])
    ):
        if "text" in block:
            text_parts.append(
                block["text"]
            )

        elif "toolUse" in block:
            tool = block["toolUse"]

            tool_calls.append({
                "id": tool["toolUseId"],
                "function": {
                    "name": tool["name"],
                    "arguments": (
                        tool.get("input") or {}
                    ),
                },
            })

    message = {
        "role": "assistant",
        "content": "\n".join(text_parts),
    }

    if tool_calls:
        message["tool_calls"] = tool_calls

    stop_reason = response.get(
        "stopReason"
    )

    return {
        "message": message,
        "done_reason": (
            "length"
            if stop_reason == "max_tokens"
            else stop_reason
        ),
        "usage": response.get(
            "usage",
            {},
        ),
    }


def _chat(
    backend,
    model,
    messages,
    tools,
    timeout,
):
    if backend == "ollama":
        return _chat_ollama(
            model,
            messages,
            tools,
            timeout,
        )

    if backend == "bedrock":
        return _chat_bedrock(
            model,
            messages,
            tools,
            timeout,
        )

    raise Incomplete(
        "invalid_model_backend",
        f"Unsupported LLM backend: {backend}",
    )


def fit_messages(messages, tools):
    # Preserve the system message and current task.
    # Remove complete historical assistant/tool groups together.
    groups = []
    dropped = False

    for message in messages[2:]:
        if message["role"] != "tool" or not groups:
            groups.append([])

        groups[-1].append(message)

    prefix = messages[:2]

    while True:
        kept_prefix = [
            dict(message)
            for message in prefix
        ]

        if dropped:
            kept_prefix[0]["content"] += (
                "\n[Earlier conversation turns omitted "
                "to fit the context budget.]"
            )

        candidate = kept_prefix + [
            message
            for group in groups
            for message in group
        ]

        size = len(
            json.dumps(
                {
                    "messages": candidate,
                    "tools": tools,
                },
                ensure_ascii=False,
            )
        )

        if size <= PROMPT_LIMIT:
            return candidate

        if len(groups) <= 1:
            raise Incomplete(
                "context_limit",
                "The current turn exceeds the prompt budget",
            )

        groups.pop(0)
        dropped = True


class LLMClient:
    def __init__(
        self,
        model,
        deadline=None,
        request_timeout=120,
        backend=None,
    ):
        self.model = model
        self.deadline = deadline or Deadline(900)
        self.request_timeout = request_timeout

        self.backend = (
            backend
            or os.environ.get(
                "SWE_LLM_BACKEND",
                "ollama",
            )
        ).strip().lower()

        if self.backend not in SUPPORTED_BACKENDS:
            raise ValueError(
                "SWE_LLM_BACKEND must be "
                "'ollama' or 'bedrock'"
            )

    def chat(self, messages, tools=None):
        result = isolated_call(
            _chat,
            (
                self.backend,
                self.model,
                fit_messages(messages, tools),
                tools,
                self.request_timeout,
            ),
            self.request_timeout,
            self.deadline,
            "model_timeout",
        )

        message = result.get("message")

        if not isinstance(message, dict):
            raise Incomplete(
                "invalid_model_response"
            )

        if (
            len(
                json.dumps(
                    message,
                    ensure_ascii=False,
                )
            )
            > 24_000
        ):
            raise Incomplete(
                "model_output_limit"
            )

        calls = message.get(
            "tool_calls"
        ) or []

        if len(calls) > 8:
            raise Incomplete(
                "tool_call_limit"
            )

        for call in calls:
            function = call.get(
                "function",
                {},
            )

            if (
                not isinstance(
                    function.get("name"),
                    str,
                )
                or not isinstance(
                    function.get("arguments"),
                    dict,
                )
            ):
                raise Incomplete(
                    "invalid_tool_call"
                )

        # Never execute potentially unfinished tool arguments.
        if result.get("done_reason") == "length":
            raise Incomplete(
                "model_output_limit",
                "Generation reached its token limit",
            )

        return result


def tool_text(result):
    return clip(
        json.dumps(
            result,
            ensure_ascii=True,
            default=str,
        ),
        TEXT_LIMIT,
    )
