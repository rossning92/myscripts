import json
import logging
import os
from typing import (
    Any,
    AsyncIterator,
    Callable,
    Dict,
    List,
    Optional,
)

import aiohttp
from ai.utils.message import Message
from ai.utils.tooluse import ToolDefinition, ToolUse
from ai.utils.usagemetadata import UsageMetadata
from utils.http import check_for_status, iter_lines

DEFAULT_MODEL = "gpt-4o"

logger = logging.getLogger(__name__)


def _to_openai_message_content(message: Message) -> List[Dict[str, Any]]:
    content = []

    if message["text"]:
        content.append(
            {
                "type": "input_text" if message["role"] == "user" else "output_text",
                "text": message["text"],
            }
        )

    image_urls = message.get("image_urls", [])
    for image_url in image_urls:
        content.append({"type": "input_image", "image_url": image_url})

    return content


def _to_openai_responses_api_input(messages: List[Message]) -> List[Dict[str, Any]]:
    input = []

    for message in messages:
        content = _to_openai_message_content(message)
        if content:
            input.append(
                {
                    "role": message["role"],
                    "content": content,
                }
            )

        for tool_use in message.get("tool_use", []):
            input.append(
                {
                    "type": "function_call",
                    "name": tool_use["tool_name"],
                    "call_id": tool_use["tool_use_id"],
                    "arguments": json.dumps(tool_use["args"]),
                }
            )

        for tool_result in message.get("tool_result", []):
            item: Dict[str, Any] = {
                "type": "function_call_output",
                "call_id": tool_result["tool_use_id"],
                "output": tool_result["content"],
            }
            input.append(item)

            # Send images from tool results as separate user messages
            for url in tool_result.get("image_urls", []):
                input.append(
                    {
                        "role": "user",
                        "content": [{"type": "input_image", "image_url": url}],
                    }
                )

    return input


async def complete_chat(
    messages: List[Message],
    out_message: Message,
    model: Optional[str] = None,
    system_prompt: Optional[str] = None,
    tools: Optional[List[ToolDefinition]] = None,
    on_tool_use_start: Optional[Callable[[ToolUse], None]] = None,
    on_tool_use: Optional[Callable[[ToolUse], None]] = None,
    usage: Optional[UsageMetadata] = None,
    base_url: str = "https://api.openai.com/v1",
    api_key: Optional[str] = None,
    reasoning_effort: Optional[str] = None,
) -> AsyncIterator[str]:
    api_key = api_key if api_key is not None else os.environ["OPENAI_API_KEY"]
    if not api_key:
        raise Exception("An OpenAI-compatible API key must be provided.")

    # https://platform.openai.com/docs/api-reference/responses
    url = f"{base_url.rstrip('/')}/responses"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    payload: Dict[str, Any] = {}

    if reasoning_effort:
        payload["reasoning"] = {"effort": reasoning_effort}
    elif model:
        # https://platform.openai.com/docs/guides/reasoning
        if model.endswith("(low)"):
            model = model[:-5]
            payload["reasoning"] = {"effort": "low"}
        elif model.endswith("(medium)"):
            model = model[:-8]
            payload["reasoning"] = {"effort": "medium"}
        elif model.endswith("(high)"):
            model = model[:-6]
            payload["reasoning"] = {"effort": "high"}

    payload.update(
        {
            "model": model if model else DEFAULT_MODEL,
            "input": _to_openai_responses_api_input(messages),
            "stream": True,
        }
    )

    if system_prompt:
        payload["instructions"] = system_prompt

    payload_tools: List[Dict[str, Any]] = []

    if tools:
        # https://platform.openai.com/docs/guides/tools?lang=bash&tool-type=function-calling
        payload_tools.extend(
            [
                {
                    "type": "function",
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": {
                        "type": "object",
                        "properties": {
                            param.name: {
                                **param.type,
                                "description": param.description,
                            }
                            for param in tool.parameters
                        },
                        "required": tool.required,
                    },
                }
                for tool in tools
            ]
        )

    if payload_tools:
        payload["tools"] = payload_tools

    logger.debug(f"payload: {payload}")

    async with aiohttp.ClientSession() as session:
        async with session.post(url, headers=headers, json=payload) as response:
            await check_for_status(response)

            async for line in iter_lines(response.content):
                line = line.rstrip(b"\n")

                if not line:
                    continue

                if line.startswith(b"data: "):
                    data = json.loads(line[6:].decode("utf-8"))
                    logger.debug(f"Received data: {data}")

                    if data["type"] == "error":
                        raise Exception(json.dumps(data))
                    elif data["type"] == "response.completed":
                        if usage:
                            u = data["response"]["usage"]
                            usage.total_tokens = u["total_tokens"]
                            usage.input_tokens = u["input_tokens"]
                            usage.output_tokens = u["output_tokens"]
                        return
                    elif data["type"] == "response.output_text.delta":
                        delta = data["delta"]
                        assert isinstance(delta, str), "Delta must be a string"
                        yield delta
                        out_message["text"] += delta
                    elif data["type"] == "response.output_item.added":
                        item = data["item"]
                        if item["type"] == "function_call":
                            tool_use = ToolUse(
                                tool_name=item["name"],
                                args={},
                                tool_use_id=item["id"],
                            )
                            if on_tool_use_start:
                                on_tool_use_start(tool_use)
                    elif data["type"] == "response.output_item.done":
                        item = data["item"]
                        if item["type"] == "function_call":
                            tool_use = ToolUse(
                                tool_name=item["name"],
                                args=json.loads(item["arguments"]),
                                tool_use_id=item["id"],
                            )
                            if on_tool_use:
                                on_tool_use(tool_use)
                            out_message.setdefault("tool_use", []).append(tool_use)
