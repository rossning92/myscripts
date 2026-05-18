import logging
import os
from typing import Any, AsyncIterator, Callable, Dict, List, Optional

import aiohttp
from ai.utils.message import Message
from ai.utils.usagemetadata import UsageMetadata
from utils.http import check_for_status

logger = logging.getLogger(__name__)

IMAGE_MODELS = ["gpt-image-2"]


async def complete_chat(
    messages: List[Message],
    out_message: Message,
    model: str,
    on_image: Optional[Callable[[str], None]] = None,
    usage: Optional[UsageMetadata] = None,
) -> AsyncIterator[str]:
    api_key = os.environ["OPENAI_API_KEY"]
    if not api_key:
        raise Exception("OPENAI_API_KEY must be provided.")

    prompt = ""
    for message in reversed(messages):
        if message["role"] == "user" and message["text"]:
            prompt = message["text"]
            break

    if not prompt:
        raise Exception("No user message found for image generation.")

    url = "https://api.openai.com/v1/images/generations"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    payload: Dict[str, Any] = {
        "model": model,
        "prompt": prompt,
        "n": 1,
        "size": "1024x1024",
        "quality": "auto",
        "output_format": "png",
    }

    logger.debug(f"payload: {payload}")

    async with aiohttp.ClientSession() as session:
        async with session.post(url, headers=headers, json=payload) as response:
            await check_for_status(response)

            body = await response.json()
            logger.debug(f"response: {body}")

            if usage:
                u = body.get("usage")
                if u:
                    usage.total_tokens = u.get("total_tokens", 0)
                    usage.input_tokens = u.get("input_tokens", 0)
                    usage.output_tokens = u.get("output_tokens", 0)

            output_format = body.get("output_format", "png")
            mime_type = {
                "png": "image/png",
                "jpeg": "image/jpeg",
                "webp": "image/webp",
            }.get(output_format, "image/png")

            for item in body.get("data", []):
                b64 = item.get("b64_json")
                if b64:
                    image_url = f"data:{mime_type};base64,{b64}"
                    out_message.setdefault("image_urls", []).append(image_url)
                    if on_image:
                        on_image(image_url)

            text = "Image generated."
            out_message["text"] = text
            yield text
