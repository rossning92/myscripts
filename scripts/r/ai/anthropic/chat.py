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
from utils.http import iter_lines
from utils.imagedataurl import parse_image_data_url

DEFAULT_MODEL = "claude-3-7-sonnet-latest"


def _to_claude_message_content(message: Message) -> List[Dict[str, Any]]:
    content = []

    if message["text"]:
        content.append({"type": "text", "text": message["text"]})

    for url in message.get("image_urls", []):
        parsed = parse_image_data_url(url)
        content.append(
            {
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": parsed.mime_type,
                    "data": parsed.data,
                },
            }
        )

    for tool_use in message.get("tool_use", []):
        content.append(
            {
                "type": "tool_use",
                "name": tool_use["tool_name"],
                "id": tool_use["tool_use_id"],
                "input": tool_use["args"],
            }
        )

    for tool_result in message.get("tool_result", []):
        result_content: Any = tool_result["content"]
        image_urls = tool_result.get("image_urls", [])
        if image_urls:
            result_content = [{"type": "text", "text": tool_result["content"]}]
            for url in image_urls:
                parsed = parse_image_data_url(url)
                result_content.append(
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": parsed.mime_type,
                            "data": parsed.data,
                        },
                    }
                )
        content.append(
            {
                "type": "tool_result",
                "tool_use_id": tool_result["tool_use_id"],
                "content": result_content,
            }
        )

    return content


async def complete_chat(
    messages: List[Message],
    out_message: Message,
    model: str = DEFAULT_MODEL,
    system_prompt: Optional[str] = None,
    tools: Optional[List[ToolDefinition]] = None,
    on_tool_use_start: Optional[Callable[[ToolUse], None]] = None,
    on_tool_use_args_delta: Optional[Callable[[str], None]] = None,
    on_tool_use: Optional[Callable[[ToolUse], None]] = None,
    usage: Optional[UsageMetadata] = None,
) -> AsyncIterator[str]:
    logging.debug(f"messages={messages}")

    api_key = os.environ["ANTHROPIC_API_KEY"]
    if not api_key:
        raise Exception("ANTHROPIC_API_KEY must be provided.")

    # https://docs.anthropic.com/en/api/messages-examples
    api_url = "https://api.anthropic.com/v1/messages"
    headers = {
        "Content-Type": "application/json",
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
    }

    payload = {
        # https://docs.anthropic.com/en/docs/about-claude/models
        "model": model,
        "messages": [
            {
                "role": message["role"],
                "content": _to_claude_message_content(message),
            }
            for message in messages
        ],
        "max_tokens": 64000,
        "stream": True,
    }
    if system_prompt:
        payload["system"] = [
            {
                "type": "text",
                "text": system_prompt,
                "cache_control": {"type": "ephemeral"},
            }
        ]
    if tools:
        payload["tools"] = [
            {
                "name": tool.name,
                "description": tool.description,
                "input_schema": {
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

    async with aiohttp.ClientSession(raise_for_status=True) as session:
        async with session.post(api_url, headers=headers, json=payload) as response:
            cb_text = None
            cb_tool_use = None
            tool_input_json = ""
            async for line in iter_lines(response.content):
                line = line.rstrip(b"\n")

                if not line:
                    continue

                if not line.startswith(b"data: "):
                    continue

                data = json.loads(line[6:].decode("utf-8"))
                logging.debug(f"Received data: {data}")

                if data["type"] == "message_start":
                    if usage:
                        u = data["message"]["usage"]
                        usage.input_tokens += u["input_tokens"]
                        usage.output_tokens += u["output_tokens"]
                        usage.cache_creation_input_tokens += u.get("cache_creation_input_tokens", 0)
                        usage.cache_read_input_tokens += u.get("cache_read_input_tokens", 0)
                        usage.total_tokens = usage.input_tokens + usage.output_tokens

                elif data["type"] == "message_delta":
                    if usage:
                        u = data["usage"]
                        usage.output_tokens += u["output_tokens"]
                        usage.total_tokens = usage.input_tokens + usage.output_tokens

                elif data["type"] == "message_stop":
                    break

                elif data["type"] == "content_block_start":
                    content_block = data["content_block"]
                    if content_block["type"] == "tool_use":
                        cb_tool_use = content_block.copy()
                        tool_input_json = ""

                        tool_use = ToolUse(
                            tool_name=cb_tool_use["name"],
                            args=cb_tool_use["input"],
                            tool_use_id=cb_tool_use["id"],
                        )
                        if on_tool_use_start:
                            on_tool_use_start(tool_use)

                    elif content_block["type"] == "text":
                        cb_text = content_block.copy()

                elif data["type"] == "content_block_delta":
                    if data["delta"]["type"] == "text_delta":
                        text_delta = data["delta"]["text"]
                        if text_delta:
                            assert isinstance(cb_text, dict)
                            cb_text["text"] += text_delta
                            yield text_delta
                            out_message["text"] += text_delta

                    if data["delta"]["type"] == "input_json_delta":
                        partial_json = data["delta"]["partial_json"]
                        tool_input_json += partial_json
                        if on_tool_use_args_delta:
                            on_tool_use_args_delta(partial_json)

                elif data["type"] == "content_block_stop":
                    if cb_text:
                        cb_text = None
                    elif cb_tool_use:
                        cb_tool_use["input"] = (
                            json.loads(tool_input_json) if tool_input_json else {}
                        )
                        tool_use = ToolUse(
                            tool_name=cb_tool_use["name"],
                            args=cb_tool_use["input"],
                            tool_use_id=cb_tool_use["id"],
                        )
                        if on_tool_use:
                            on_tool_use(tool_use)
                        out_message.setdefault("tool_use", []).append(tool_use)
                        cb_tool_use = None
                        tool_input_json = ""

                elif data["type"] == "error":
                    raise Exception(f"Error from API: {data}")
