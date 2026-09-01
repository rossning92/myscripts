import asyncio
from typing import AsyncIterator

import aiohttp


_RETRYABLE_ERROR_TYPES = (
    aiohttp.ClientConnectionError,
    aiohttp.ClientPayloadError,
    asyncio.TimeoutError,
)


def is_retryable_error(exception: BaseException) -> bool:
    return isinstance(exception, _RETRYABLE_ERROR_TYPES)


async def check_for_status(response):
    if response.status >= 400:
        error_text = await response.text()
        raise Exception(f"Request failed with status {response.status}: {error_text}")


async def iter_lines(
    content: aiohttp.StreamReader,
    chunk_size: int = 64 * 1024,
) -> AsyncIterator[bytes]:
    buffer = b""
    async for chunk in content.iter_chunked(chunk_size):
        buffer += chunk

        while b"\n" in buffer:
            line, buffer = buffer.split(b"\n", 1)
            yield line

    if buffer:
        yield buffer
