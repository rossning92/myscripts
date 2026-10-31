from datetime import datetime

from ai.chat import complete_chat
from ai.utils.message import Message

MODEL = "openai:gpt-5.6-luna-low"
TITLE_MAX_CHARS = 36
PROMPT_MAX_BYTES = 960

_INSTRUCTIONS = (
    "Generate a concise, single-line task title of at most 36 characters and "
    "under five words where possible. Start with an imperative verb. Capitalize "
    "only the first word unless the user's language, proper nouns, acronyms, or "
    "code terms require otherwise. Preserve ticket references exactly. Write in "
    "the user's language. Do not use quotes, markdown, or trailing punctuation. "
    "Do not answer the request."
)


def _truncate_utf8(text: str, max_bytes: int) -> str:
    return text.encode("utf-8")[:max_bytes].decode("utf-8", errors="ignore")


def _normalize_title(title: str) -> str:
    title = " ".join(title.strip().strip("`\"'“”‘’").split())
    title = title.rstrip(".?!").rstrip()
    return title[:TITLE_MAX_CHARS]


def get_fallback_title(prompt: str) -> str:
    return _normalize_title(prompt)


async def generate_title(prompt: str) -> str:
    prefix = f"{_INSTRUCTIONS}\n\nUser prompt:\n"
    prompt = _truncate_utf8(
        prompt.strip(), PROMPT_MAX_BYTES - len(prefix.encode("utf-8"))
    )
    if not prompt:
        return ""

    out_message = Message(
        role="assistant",
        text="",
        timestamp=datetime.now().timestamp(),
    )
    messages = [
        Message(
            role="user",
            text=prefix + prompt,
            timestamp=datetime.now().timestamp(),
        )
    ]

    async for _ in await complete_chat(
        messages=messages,
        out_message=out_message,
        model=MODEL,
    ):
        pass

    return _normalize_title(out_message["text"])
