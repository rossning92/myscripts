import os
from typing import (
    AsyncIterator,
    Callable,
    List,
    Optional,
)

import ai.anthropic.chat
import ai.gemini.chat
import ai.openai.chat
import ai.openai_compatible.chat
import ai.openai_image.chat
import ai.openrouter.chat
from ai.utils.message import Message
from ai.utils.tooluse import ToolDefinition, ToolResult, ToolUse
from ai.utils.usagemetadata import UsageMetadata
from utils.textutil import truncate_text


def get_image_url_text(image_url: str) -> str:
    return "\033[34m▣ image: {}\033[0m".format(image_url[:32] + "...")


def get_context_text(context: str) -> str:
    return "\033[34m≡ context: “{}”\033[0m".format(truncate_text(context))


def get_tool_result_text(tool_result: ToolResult) -> str:
    return "\033[34m└ {}\033[0m".format(truncate_text(tool_result["content"]))


def get_tool_use_text(tool_use: ToolUse) -> str:
    tool_name = tool_use["tool_name"]
    args = truncate_text(str(tool_use["args"]))
    return "\033[34m● \033[1m{}\033[22m: {}\033[0m".format(tool_name, args)


def get_reasoning_text(text: str) -> str:
    return "\033[34m… reasoning: {}\033[0m".format(truncate_text(text))


async def complete_chat(
    messages: List[Message],
    out_message: Message,
    model: Optional[str] = None,
    system_prompt: Optional[str] = None,
    tools: Optional[List[ToolDefinition]] = None,
    on_image: Optional[Callable[[str], None]] = None,
    on_tool_use_start: Optional[Callable[[ToolUse], None]] = None,
    on_tool_use_args_delta: Optional[Callable[[str], None]] = None,
    on_tool_use: Optional[Callable[[ToolUse], None]] = None,
    on_reasoning: Optional[Callable[[str], None]] = None,
    usage: Optional[UsageMetadata] = None,
) -> AsyncIterator[str]:
    OPENROUTER_PREFIX = "openrouter:"

    if model and model.startswith("claude"):
        return ai.anthropic.chat.complete_chat(
            messages=messages,
            out_message=out_message,
            model=model,
            system_prompt=system_prompt,
            tools=tools,
            on_tool_use_start=on_tool_use_start,
            on_tool_use_args_delta=on_tool_use_args_delta,
            on_tool_use=on_tool_use,
            usage=usage,
        )
    elif model and model.startswith(OPENROUTER_PREFIX):
        model = model[len(OPENROUTER_PREFIX) :]

        return await ai.openrouter.chat.complete_chat(
            messages=messages,
            out_message=out_message,
            model=model,
            system_prompt=system_prompt,
            tools=tools,
            on_image=on_image,
            on_tool_use=on_tool_use,
            on_reasoning=on_reasoning,
            usage=usage,
        )
    elif model and model.startswith("gemini"):
        return ai.gemini.chat.complete_chat(
            messages=messages,
            out_message=out_message,
            model=model,
            system_prompt=system_prompt,
            tools=tools,
            on_image=on_image,
            on_tool_use=on_tool_use,
            usage=usage,
        )
    elif model and model in ai.openai_image.chat.IMAGE_MODELS:
        return ai.openai_image.chat.complete_chat(
            messages=messages,
            out_message=out_message,
            model=model,
            on_image=on_image,
            usage=usage,
        )
    elif model and model.startswith("deepseek"):
        return ai.openai_compatible.chat.complete_chat(
            endpoint_url="https://api.deepseek.com/chat/completions",
            api_key=os.environ["DEEPSEEK_API_KEY"],
            messages=messages,
            out_message=out_message,
            model=model,
            system_prompt=system_prompt,
            tools=tools,
            on_tool_use=on_tool_use,
            on_reasoning=on_reasoning,
            usage=usage,
        )
    elif model == "llama_cpp":
        return ai.openai_compatible.chat.complete_chat(
            endpoint_url=os.environ.get(
                "LLAMA_CPP_ENDPOINT",
                "http://127.0.0.1:8080/v1/chat/completions",
            ),
            api_key=os.environ.get("LLAMA_CPP_API_KEY", "no-key"),
            messages=messages,
            out_message=out_message,
            model=os.environ.get(
                "LLAMA_CPP_MODEL",
                "Qwen/Qwen3-1.7B-GGUF",
            ),
            system_prompt=system_prompt,
            tools=tools,
            on_tool_use=on_tool_use,
            on_reasoning=on_reasoning,
            usage=usage,
        )
    else:
        return ai.openai.chat.complete_chat(
            messages=messages,
            out_message=out_message,
            model=model,
            system_prompt=system_prompt,
            tools=tools,
            on_tool_use_start=on_tool_use_start,
            on_tool_use=on_tool_use,
            usage=usage,
        )
