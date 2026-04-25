import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from deepseek_client import deepseek_chat_completion


@pytest.mark.asyncio
async def test_deepseek_chat_completion_success():
    mock_response = AsyncMock()
    mock_response.status = 200
    mock_response.text = AsyncMock(return_value="")
    mock_response.json = AsyncMock(
        return_value={"choices": [{"message": {"content": "hello from model"}}]}
    )
    post_ctx = MagicMock()
    post_ctx.__aenter__ = AsyncMock(return_value=mock_response)
    post_ctx.__aexit__ = AsyncMock(return_value=None)
    session = AsyncMock()
    session.post = MagicMock(return_value=post_ctx)
    session_ctx = MagicMock()
    session_ctx.__aenter__ = AsyncMock(return_value=session)
    session_ctx.__aexit__ = AsyncMock(return_value=None)

    with patch("deepseek_client.aiohttp.ClientSession", return_value=session_ctx):
        out = await deepseek_chat_completion("key", {"messages": []})

    assert out == "hello from model"
    session.post.assert_called_once()


@pytest.mark.asyncio
async def test_deepseek_chat_completion_non_200():
    mock_response = AsyncMock()
    mock_response.status = 429
    mock_response.text = AsyncMock(return_value="too many requests")
    post_ctx = MagicMock()
    post_ctx.__aenter__ = AsyncMock(return_value=mock_response)
    post_ctx.__aexit__ = AsyncMock(return_value=None)
    session = AsyncMock()
    session.post = MagicMock(return_value=post_ctx)
    session_ctx = MagicMock()
    session_ctx.__aenter__ = AsyncMock(return_value=session)
    session_ctx.__aexit__ = AsyncMock(return_value=None)

    with patch("deepseek_client.aiohttp.ClientSession", return_value=session_ctx):
        out = await deepseek_chat_completion("key", {"messages": []})

    assert "Sorry" in out


@pytest.mark.asyncio
async def test_deepseek_chat_completion_timeout():
    post_ctx = MagicMock()
    post_ctx.__aenter__ = AsyncMock(side_effect=asyncio.TimeoutError())
    post_ctx.__aexit__ = AsyncMock(return_value=None)
    session = AsyncMock()
    session.post = MagicMock(return_value=post_ctx)
    session_ctx = MagicMock()
    session_ctx.__aenter__ = AsyncMock(return_value=session)
    session_ctx.__aexit__ = AsyncMock(return_value=None)

    with patch("deepseek_client.aiohttp.ClientSession", return_value=session_ctx):
        out = await deepseek_chat_completion("key", {"messages": []})

    assert "too long" in out.lower()
