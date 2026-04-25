"""HTTP client for DeepSeek chat completions (timeouts + error handling)."""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict

import aiohttp

logger = logging.getLogger(__name__)

CHAT_COMPLETIONS_URL = "https://api.deepseek.com/v1/chat/completions"
DEFAULT_TIMEOUT = aiohttp.ClientTimeout(total=90, connect=15, sock_read=75)


async def deepseek_chat_completion(api_key: str, payload: Dict[str, Any]) -> str:
    """
    POST /v1/chat/completions. Returns assistant message text, or a short user-facing error string.
    """
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    try:
        async with aiohttp.ClientSession(timeout=DEFAULT_TIMEOUT) as session:
            async with session.post(
                CHAT_COMPLETIONS_URL, headers=headers, json=payload
            ) as response:
                if response.status == 200:
                    result = await response.json()
                    return result["choices"][0]["message"]["content"]
                error_text = await response.text()
                snippet = (error_text[:200] + "…") if len(error_text) > 200 else error_text
                logger.error(
                    "DeepSeek API error %s (body snippet): %s",
                    response.status,
                    snippet,
                )
                return (
                    "Sorry, I encountered an error with the grammar service. "
                    "Please try again later."
                )
    except asyncio.TimeoutError:
        logger.error("DeepSeek API request timed out")
        return (
            "Sorry, the grammar service took too long to respond. Please try again."
        )
    except aiohttp.ClientError as e:
        logger.error("Network error calling DeepSeek API: %s", e)
        return (
            "Sorry, I encountered an error with the grammar service. "
            "Please try again later."
        )
