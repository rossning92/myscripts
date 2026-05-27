import json
import logging
import os
from typing import AsyncIterator, Callable, Dict, List, Optional

import aiohttp
from ai.utils.message import Message
from ai.utils.tooluse import ToolDefinition, ToolUse
from ai.utils.usagemetadata import UsageMetadata
from utils.http import check_for_status, iter_lines


async def complete_chat(
    messages: List[Message],
    out_message: Message,
    endpoint_url: str,
    api_key: str,
    model: Optional[str] = None,
    system_prompt: Optional[str] = None,
    tools: Optional[List[ToolDefinition]] = None,
    on_image: Optional[Callable[[str], None]] = None,
    on_tool_use: Optional[Callable[[ToolUse], None]] = None,
    on_reasoning: Optional[Callable[[str], None]] = None,
    extra_payload: Optional[Dict] = None,
    usage: Optional[UsageMetadata] = None,
) -> AsyncIterator[str]:
    logging.debug(f"messages: {messages}")

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    payload: dict = {
        "model": model or os.environ.get("OPENROUTER_MODEL", "openai/gpt-4o-mini"),
        "messages": [],
        "stream": True,
        "stream_options": {"include_usage": True},
    }

    if tools:
        # https://openrouter.ai/docs/features/tool-calling
        payload["tools"] = [
            {
                "type": "function",
                "function": {
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
                },
            }
            for tool in tools
        ]

    if system_prompt:
        payload["messages"].append({"role": "system", "content": system_prompt})

    for message in messages:
        # Message
        if message["text"] or message.get("tool_use"):
            m = {
                "role": message["role"],
                "content": [
                    {"type": "text", "text": message["text"]},
                ]
                + [
                    {"type": "image_url", "image_url": {"url": url}}
                    for url in message.get("image_urls", [])
                ],
                **(
                    {
                        "tool_calls": [
                            {
                                "id": tool_use["tool_use_id"],
                                "type": "function",
                                "function": {
                                    "name": tool_use["tool_name"],
                                    "arguments": json.dumps(tool_use["args"]),
                                },
                            }
                            for tool_use in message["tool_use"]
                        ]
                    }
                    if "tool_use" in message
                    else {}
                ),
            }

            if "reasoning_details" in message:
                m["reasoning_details"] = message["reasoning_details"]

            payload["messages"].append(m)

        # Tool call result
        for tool_result in message.get("tool_result", []):
            payload["messages"].append(
                {
                    "role": "tool",
                    "tool_call_id": tool_result["tool_use_id"],
                    "content": tool_result["content"],
                }
            )

            # Send images from tool results as separate user messages
            for url in tool_result.get("image_urls", []):
                payload["messages"].append(
                    {
                        "role": "user",
                        "content": [
                            {"type": "image_url", "image_url": {"url": url}},
                        ],
                    }
                )

    if extra_payload:
        payload.update(extra_payload)

    logging.debug(f"payload: {payload}")

    async with aiohttp.ClientSession() as session:
        async with session.post(
            endpoint_url,
            headers=headers,
            json=payload,
        ) as response:
            await check_for_status(response)

            pending_tool_calls: Dict[int, dict] = {}
            pending_reasoning = ""

            def flush_reasoning():
                nonlocal pending_reasoning
                if pending_reasoning:
                    if on_reasoning:
                        on_reasoning(pending_reasoning)
                    out_message.setdefault("reasoning", []).append(
                        pending_reasoning
                    )
                    pending_reasoning = ""

            def flush_tool_calls():
                for idx in sorted(pending_tool_calls):
                    tc = pending_tool_calls[idx]
                    raw_args = tc["arguments"]
                    tool_use = ToolUse(
                        tool_name=tc["name"],
                        args=json.loads(raw_args) if raw_args else {},
                        tool_use_id=tc["id"],
                    )
                    if on_tool_use:
                        on_tool_use(tool_use)
                    out_message.setdefault("tool_use", []).append(tool_use)
                pending_tool_calls.clear()

            async for line in iter_lines(response.content):
                if not line:
                    continue

                if not line.startswith(b"data: "):
                    continue

                data_str = line[6:].decode("utf-8")
                if data_str == "[DONE]":
                    flush_reasoning()
                    flush_tool_calls()
                    return

                try:
                    data = json.loads(data_str)
                    logging.debug(f"data: {data}")
                except json.JSONDecodeError:
                    logging.debug(f"Skipping malformed chunk: {data_str}")
                    continue

                if "usage" in data:
                    if usage:
                        u = data["usage"]
                        usage.total_tokens = u["total_tokens"]
                        usage.input_tokens = u["prompt_tokens"]
                        usage.output_tokens = u["completion_tokens"]

                for choice in data.get("choices", []):
                    delta = choice.get("delta", {})
                    finish_reason = choice.get("finish_reason")

                    # Accumulate reasoning deltas
                    reasoning_details = delta.get("reasoning_details")
                    if reasoning_details:
                        assert isinstance(reasoning_details, list)
                        for reasoning_detail in reasoning_details:
                            if reasoning_detail["type"] == "reasoning.text":
                                pending_reasoning += reasoning_detail["text"]
                        out_message.setdefault("reasoning_details", []).extend(
                            reasoning_details
                        )

                    # Accumulate tool call deltas
                    tool_calls = delta.get("tool_calls")
                    if tool_calls:
                        logging.debug(f"tool call delta: {tool_calls}")
                        for tool_call in tool_calls:
                            idx = tool_call["index"]
                            if idx not in pending_tool_calls:
                                pending_tool_calls[idx] = {
                                    "id": tool_call.get("id", ""),
                                    "name": "",
                                    "arguments": "",
                                }
                            tc = pending_tool_calls[idx]
                            function = tool_call.get("function") or {}
                            if function.get("name"):
                                tc["name"] = function["name"]
                            if function.get("arguments"):
                                tc["arguments"] += function["arguments"]

                    # Stream content chunks, flushing reasoning first
                    content = delta.get("content")
                    if content:
                        flush_reasoning()
                        logging.debug(f"yielding content chunk: {content}")
                        yield content
                        out_message["text"] += content

                    # On finish, flush all pending state
                    if finish_reason:
                        flush_reasoning()
                        flush_tool_calls()

                    images = delta.get("images")
                    if images:
                        assert isinstance(images, list)
                        for image in images:
                            if image["type"] == "image_url":
                                image_url: str = image["image_url"]["url"]
                                if on_image:
                                    on_image(image_url)
                                out_message.setdefault("image_urls", []).append(
                                    image_url
                                )
