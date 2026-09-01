from datetime import datetime

from ai.chat import complete_chat
from ai.utils.message import Message

MODEL = "openai:gpt-4.1-nano"

_SYSTEM_PROMPT = (
    "Summarize the user's request as a short terminal title. "
    "Return only the title, without quotes, markdown, or punctuation at the end. "
    "Use at most 8 words."
)


def get_fallback_title(prompt: str) -> str:
    return " ".join(prompt.split())


async def generate_title(prompt: str) -> str:
    out_message = Message(
        role="assistant",
        text="",
        timestamp=datetime.now().timestamp(),
    )
    messages = [
        Message(
            role="user",
            text=prompt,
            timestamp=datetime.now().timestamp(),
        )
    ]

    async for _ in await complete_chat(
        messages=messages,
        out_message=out_message,
        model=MODEL,
        system_prompt=_SYSTEM_PROMPT,
    ):
        pass

    return " ".join(out_message["text"].split()).strip(" `\"'.")
