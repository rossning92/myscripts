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
import ai.utils.tools.bash
import ai.utils.tools.edit
import ai.utils.tools.read
import ai.utils.tools.web_fetch
import ai.utils.tools.web_search
from ai.models import get_model
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
    args = tool_use["args"]
    preview_getters = {
        "bash": ai.utils.tools.bash.get_tool_use_preview,
        "edit": ai.utils.tools.edit.get_tool_use_preview,
        "read": ai.utils.tools.read.get_tool_use_preview,
        "web_fetch": ai.utils.tools.web_fetch.get_tool_use_preview,
        "web_search": ai.utils.tools.web_search.get_tool_use_preview,
    }
    preview = preview_getters.get(tool_name, str)(args)
    args_text = truncate_text(preview)
    return "\033[34m• \033[1m{}\033[22m: {}\033[0m".format(tool_name, args_text)


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
    selected_model = get_model(model)

    if selected_model.api_type == "anthropic_messages":
        return ai.anthropic.chat.complete_chat(
            messages=messages,
            out_message=out_message,
            model=selected_model.model,
            system_prompt=system_prompt,
            tools=tools,
            on_tool_use_start=on_tool_use_start,
            on_tool_use_args_delta=on_tool_use_args_delta,
            on_tool_use=on_tool_use,
            usage=usage,
        )
    elif selected_model.api_type == "openai_responses":
        return ai.openai.chat.complete_chat(
            messages=messages,
            out_message=out_message,
            model=selected_model.model,
            system_prompt=system_prompt,
            tools=tools,
            on_tool_use_start=on_tool_use_start,
            on_tool_use=on_tool_use,
            usage=usage,
            **(
                {"base_url": selected_model.base_url}
                if selected_model.base_url
                else {}
            ),
            api_key=selected_model.api_key,
            reasoning_effort=selected_model.reasoning_effort,
        )
    elif selected_model.api_type == "gemini_generate_content":
        return ai.gemini.chat.complete_chat(
            messages=messages,
            out_message=out_message,
            model=selected_model.model,
            system_prompt=system_prompt,
            tools=tools,
            on_image=on_image,
            on_tool_use=on_tool_use,
            usage=usage,
        )
    elif selected_model.api_type == "openai_images":
        return ai.openai_image.chat.complete_chat(
            messages=messages,
            out_message=out_message,
            model=selected_model.model,
            on_image=on_image,
            usage=usage,
        )
    elif selected_model.api_type == "openai_chat_completions":
        if not selected_model.base_url:
            raise ValueError(f"Model {selected_model.id!r} requires a base URL")
        if not selected_model.api_key:
            raise ValueError(f"Model {selected_model.id!r} requires an API key")
        endpoint_url = selected_model.base_url.rstrip("/")
        if not endpoint_url.endswith("/chat/completions"):
            endpoint_url += "/chat/completions"

        extra_payload = {}
        if selected_model.reasoning_effort:
            extra_payload.setdefault("extra_body", {})["reasoning"] = {
                "effort": selected_model.reasoning_effort
            }
        return ai.openai_compatible.chat.complete_chat(
            endpoint_url=endpoint_url,
            api_key=selected_model.api_key,
            messages=messages,
            out_message=out_message,
            model=selected_model.model,
            system_prompt=system_prompt,
            tools=tools,
            on_image=on_image,
            on_tool_use=on_tool_use,
            on_reasoning=on_reasoning,
            extra_payload=extra_payload,
            usage=usage,
        )

    raise ValueError(f"Unsupported API type: {selected_model.api_type}")
