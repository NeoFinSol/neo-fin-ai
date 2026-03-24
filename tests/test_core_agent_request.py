"""Tests for Agent.request method — covers the aiohttp HTTP call paths."""
import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from aiohttp import ClientError, ContentTypeError

from src.core.agent import Agent, ConfigurationError


class TestAgentRequestHTTP:
    """Tests for Agent.request — covers lines 115-203."""

    @pytest.mark.asyncio
    async def test_request_success_with_response_key(self):
        """Successful request returns response field from JSON."""
        agent = Agent()
        agent.set_config("token", "https://api.example.com")

        mock_response = AsyncMock()
        mock_response.json = AsyncMock(return_value={"response": "Hello from Qwen"})
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=False)

        mock_session = AsyncMock()
        mock_session.post = MagicMock(return_value=mock_response)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        with patch("aiohttp.ClientSession", return_value=mock_session):
            result = await agent.request("chat1", "Hello")
            assert result == "Hello from Qwen"

    @pytest.mark.asyncio
    async def test_request_unexpected_response_format(self):
        """Non-dict response falls back to string conversion."""
        agent = Agent()
        agent.set_config("token", "https://api.example.com")

        mock_response = AsyncMock()
        mock_response.json = AsyncMock(return_value=["unexpected", "list"])
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=False)

        mock_session = AsyncMock()
        mock_session.post = MagicMock(return_value=mock_response)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        with patch("aiohttp.ClientSession", return_value=mock_session):
            result = await agent.request("chat1", "Hello")
            assert result is not None  # fallback string

    @pytest.mark.asyncio
    async def test_request_content_type_error_returns_text(self):
        """ContentTypeError falls back to text response."""
        agent = Agent()
        agent.set_config("token", "https://api.example.com")

        mock_response = AsyncMock()
        mock_response.json = AsyncMock(side_effect=ContentTypeError(MagicMock(), MagicMock()))
        mock_response.text = AsyncMock(return_value="plain text response")
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=False)

        mock_session = AsyncMock()
        mock_session.post = MagicMock(return_value=mock_response)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        with patch("aiohttp.ClientSession", return_value=mock_session):
            result = await agent.request("chat1", "Hello")
            assert result == "plain text response"

    @pytest.mark.asyncio
    async def test_request_client_error_retries_then_returns_none(self):
        """ClientError triggers retries, returns None after all fail."""
        agent = Agent()
        agent.set_config("token", "https://api.example.com")

        with patch("aiohttp.ClientSession", side_effect=ClientError("network error")), \
             patch("asyncio.sleep", new_callable=AsyncMock):
            result = await agent.request("chat1", "Hello", retries=2)
            assert result is None

    @pytest.mark.asyncio
    async def test_request_timeout_raises_after_retries(self):
        """TimeoutError raises after all retries exhausted."""
        agent = Agent()
        agent.set_config("token", "https://api.example.com")

        with patch("aiohttp.ClientSession", side_effect=asyncio.TimeoutError()), \
             patch("asyncio.sleep", new_callable=AsyncMock):
            with pytest.raises(asyncio.TimeoutError):
                await agent.request("chat1", "Hello", retries=2)

    @pytest.mark.asyncio
    async def test_request_unexpected_exception_returns_none(self):
        """Unexpected exception returns None after retries."""
        agent = Agent()
        agent.set_config("token", "https://api.example.com")

        with patch("aiohttp.ClientSession", side_effect=RuntimeError("unexpected")), \
             patch("asyncio.sleep", new_callable=AsyncMock):
            result = await agent.request("chat1", "Hello", retries=2)
            assert result is None

    @pytest.mark.asyncio
    async def test_request_with_system_and_parent_id(self):
        """Request includes system and parent_id in payload."""
        agent = Agent()
        agent.set_config("token", "https://api.example.com")

        mock_response = AsyncMock()
        mock_response.json = AsyncMock(return_value={"response": "ok"})
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=False)

        mock_session = AsyncMock()
        mock_session.post = MagicMock(return_value=mock_response)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        with patch("aiohttp.ClientSession", return_value=mock_session):
            result = await agent.request(
                "chat1", "Hello",
                system="Be helpful",
                parent_id="msg-001"
            )
            assert result == "ok"
            # Verify the call was made with correct JSON
            call_kwargs = mock_session.post.call_args[1]
            assert call_kwargs["json"]["system"] == "Be helpful"
            assert call_kwargs["json"]["parent_id"] == "msg-001"

    @pytest.mark.asyncio
    async def test_request_dict_without_response_key_returns_string(self):
        """Dict response without 'response' key falls back to string."""
        agent = Agent()
        agent.set_config("token", "https://api.example.com")

        mock_response = AsyncMock()
        mock_response.json = AsyncMock(return_value={"error": "something"})
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=False)

        mock_session = AsyncMock()
        mock_session.post = MagicMock(return_value=mock_response)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        with patch("aiohttp.ClientSession", return_value=mock_session):
            result = await agent.request("chat1", "Hello")
            assert result is not None
