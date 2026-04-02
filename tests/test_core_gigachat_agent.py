"""Tests for core/gigachat_agent.py — GigaChat API agent."""
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.core.gigachat_agent import GigaChatAgent


class TestGigaChatAgentInit:
    def test_default_state(self):
        agent = GigaChatAgent()
        assert agent._configured is False
        assert agent._client_id is None
        assert agent._client_secret is None
        assert agent._auth_token is None
        assert agent.model == "GigaChat-Pro"

    def test_custom_timeout(self):
        agent = GigaChatAgent(timeout=60)
        assert agent.timeout == 60


class TestGigaChatAgentSetConfig:
    def test_valid_config(self):
        agent = GigaChatAgent()
        agent.set_config("client-id", "client-secret")
        assert agent._configured is True
        assert agent._client_id == "client-id"
        assert agent._client_secret == "client-secret"

    def test_strips_whitespace(self):
        agent = GigaChatAgent()
        agent.set_config("  cid  ", "  csec  ")
        assert agent._client_id == "cid"
        assert agent._client_secret == "csec"

    def test_empty_client_id_raises(self):
        agent = GigaChatAgent()
        with pytest.raises(ValueError, match="Client ID is required"):
            agent.set_config("", "secret")

    def test_none_client_id_raises(self):
        agent = GigaChatAgent()
        with pytest.raises(ValueError, match="Client ID is required"):
            agent.set_config(None, "secret")

    def test_empty_client_secret_raises(self):
        agent = GigaChatAgent()
        with pytest.raises(ValueError, match="Client Secret is required"):
            agent.set_config("cid", "")

    def test_none_client_secret_raises(self):
        agent = GigaChatAgent()
        with pytest.raises(ValueError, match="Client Secret is required"):
            agent.set_config("cid", None)

    def test_custom_urls(self):
        agent = GigaChatAgent()
        agent.set_config("cid", "csec", auth_url="https://auth.test/", chat_url="https://chat.test/")
        assert agent._auth_url == "https://auth.test"
        assert agent._chat_url == "https://chat.test"


class TestGigaChatAgentEnsureConfigured:
    def test_raises_when_not_configured(self):
        agent = GigaChatAgent()
        with pytest.raises(ValueError, match="not configured"):
            agent._ensure_configured()

    def test_no_error_when_configured(self):
        agent = GigaChatAgent()
        agent.set_config("cid", "csec")
        agent._ensure_configured()  # should not raise


class TestGigaChatAgentGetAccessToken:
    @pytest.mark.asyncio
    async def test_returns_cached_token(self):
        import time
        agent = GigaChatAgent()
        agent.set_config("cid", "csec")
        agent._auth_token = "cached-token"
        agent._token_expires_at = time.time() + 3600

        result = await agent._get_access_token()
        assert result == "cached-token"

    @pytest.mark.asyncio
    async def test_fetches_new_token_on_success(self):
        agent = GigaChatAgent()
        agent.set_config("cid", "csec")

        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={"access_token": "new-token", "expires_in": 3600})
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=False)

        mock_session = AsyncMock()
        mock_session.post = MagicMock(return_value=mock_response)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        mock_connector = MagicMock()
        with patch("aiohttp.ClientSession", return_value=mock_session), \
             patch("aiohttp.TCPConnector", return_value=mock_connector):
            result = await agent._get_access_token()
            assert result == "new-token"
            assert agent._auth_token == "new-token"

    @pytest.mark.asyncio
    async def test_raises_on_auth_failure(self):
        agent = GigaChatAgent()
        agent.set_config("cid", "csec")

        mock_response = AsyncMock()
        mock_response.status = 401
        mock_response.text = AsyncMock(return_value="Unauthorized")
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=False)

        mock_session = AsyncMock()
        mock_session.post = MagicMock(return_value=mock_response)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        mock_connector = MagicMock()
        with patch("aiohttp.ClientSession", return_value=mock_session), \
             patch("aiohttp.TCPConnector", return_value=mock_connector):
            with pytest.raises(ValueError, match="authentication failed"):
                await agent._get_access_token()

    @pytest.mark.asyncio
    async def test_raises_on_missing_token_in_response(self):
        agent = GigaChatAgent()
        agent.set_config("cid", "csec")

        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={"expires_in": 3600})  # no access_token
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=False)

        mock_session = AsyncMock()
        mock_session.post = MagicMock(return_value=mock_response)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        mock_connector = MagicMock()
        with patch("aiohttp.ClientSession", return_value=mock_session), \
             patch("aiohttp.TCPConnector", return_value=mock_connector):
            with pytest.raises(ValueError, match="No access_token"):
                await agent._get_access_token()

    @pytest.mark.asyncio
    async def test_raises_on_connection_error(self):
        import aiohttp
        agent = GigaChatAgent()
        agent.set_config("cid", "csec")

        mock_connector = MagicMock()
        with patch("aiohttp.TCPConnector", return_value=mock_connector), \
             patch("aiohttp.ClientSession", side_effect=aiohttp.ClientError("conn failed")):
            with pytest.raises(ValueError, match="auth connection error"):
                await agent._get_access_token()


class TestGigaChatAgentInvoke:
    @pytest.mark.asyncio
    async def test_invoke_not_configured_raises(self):
        agent = GigaChatAgent()
        with pytest.raises(ValueError, match="not configured"):
            await agent.invoke({"tool_input": "test"})

    @pytest.mark.asyncio
    async def test_invoke_delegates_to_request(self):
        agent = GigaChatAgent()
        agent.set_config("cid", "csec")

        with patch.object(agent, "request", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = "GigaChat response"
            result = await agent.invoke({"tool_input": "hello", "system": "be helpful"})
            assert result == "GigaChat response"
            mock_req.assert_called_once_with(messages="hello", system="be helpful")

    @pytest.mark.asyncio
    async def test_invoke_timeout_raises(self):
        agent = GigaChatAgent()
        agent.set_config("cid", "csec")

        with patch.object(agent, "request", new_callable=AsyncMock) as mock_req:
            mock_req.side_effect = asyncio.TimeoutError()
            with pytest.raises(asyncio.TimeoutError):
                await agent.invoke({"tool_input": "test"}, timeout=1)


class TestGigaChatAgentRequest:
    @pytest.mark.asyncio
    async def test_request_not_configured_raises(self):
        agent = GigaChatAgent()
        with pytest.raises(ValueError, match="not configured"):
            await agent.request("hello")

    @pytest.mark.asyncio
    async def test_request_success(self):
        agent = GigaChatAgent()
        agent.set_config("cid", "csec")

        with patch.object(agent, "_get_access_token", new_callable=AsyncMock) as mock_token:
            mock_token.return_value = "access-token"

            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.json = AsyncMock(return_value={
                "choices": [{"message": {"role": "assistant", "content": "Hello!"}}]
            })
            mock_response.__aenter__ = AsyncMock(return_value=mock_response)
            mock_response.__aexit__ = AsyncMock(return_value=False)

            mock_session = AsyncMock()
            mock_session.post = MagicMock(return_value=mock_response)
            mock_session.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session.__aexit__ = AsyncMock(return_value=False)

            mock_connector = MagicMock()
            with patch("aiohttp.ClientSession", return_value=mock_session), \
                 patch("aiohttp.TCPConnector", return_value=mock_connector):
                result = await agent.request("hello")
                assert result == "Hello!"

    @pytest.mark.asyncio
    async def test_request_401_clears_token(self):
        agent = GigaChatAgent()
        agent.set_config("cid", "csec")
        agent._auth_token = "old-token"

        with patch.object(agent, "_get_access_token", new_callable=AsyncMock) as mock_token:
            mock_token.return_value = "access-token"

            mock_response = AsyncMock()
            mock_response.status = 401
            mock_response.text = AsyncMock(return_value="Unauthorized")
            mock_response.__aenter__ = AsyncMock(return_value=mock_response)
            mock_response.__aexit__ = AsyncMock(return_value=False)

            mock_session = AsyncMock()
            mock_session.post = MagicMock(return_value=mock_response)
            mock_session.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session.__aexit__ = AsyncMock(return_value=False)

            mock_connector = MagicMock()
            with patch("aiohttp.ClientSession", return_value=mock_session), \
                 patch("aiohttp.TCPConnector", return_value=mock_connector):
                result = await agent.request("hello", retries=1)
                assert result is None
                assert agent._auth_token is None

    @pytest.mark.asyncio
    async def test_request_empty_choices_returns_none(self):
        agent = GigaChatAgent()
        agent.set_config("cid", "csec")

        with patch.object(agent, "_get_access_token", new_callable=AsyncMock) as mock_token:
            mock_token.return_value = "access-token"

            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.json = AsyncMock(return_value={"choices": []})
            mock_response.__aenter__ = AsyncMock(return_value=mock_response)
            mock_response.__aexit__ = AsyncMock(return_value=False)

            mock_session = AsyncMock()
            mock_session.post = MagicMock(return_value=mock_response)
            mock_session.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session.__aexit__ = AsyncMock(return_value=False)

            mock_connector = MagicMock()
            with patch("aiohttp.ClientSession", return_value=mock_session), \
                 patch("aiohttp.TCPConnector", return_value=mock_connector):
                result = await agent.request("hello", retries=1)
                assert result is None

    @pytest.mark.asyncio
    async def test_request_with_system_prompt(self):
        agent = GigaChatAgent()
        agent.set_config("cid", "csec")

        with patch.object(agent, "_get_access_token", new_callable=AsyncMock) as mock_token:
            mock_token.return_value = "access-token"

            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.json = AsyncMock(return_value={
                "choices": [{"message": {"role": "assistant", "content": "Sure!"}}]
            })
            mock_response.__aenter__ = AsyncMock(return_value=mock_response)
            mock_response.__aexit__ = AsyncMock(return_value=False)

            mock_session = AsyncMock()
            mock_session.post = MagicMock(return_value=mock_response)
            mock_session.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session.__aexit__ = AsyncMock(return_value=False)

            mock_connector = MagicMock()
            with patch("aiohttp.ClientSession", return_value=mock_session), \
                 patch("aiohttp.TCPConnector", return_value=mock_connector):
                result = await agent.request("hello", system="Be concise")
                assert result == "Sure!"

    @pytest.mark.asyncio
    async def test_request_client_error_returns_none_after_retries(self):
        import aiohttp
        agent = GigaChatAgent()
        agent.set_config("cid", "csec")

        with patch.object(agent, "_get_access_token", new_callable=AsyncMock) as mock_token:
            mock_token.return_value = "access-token"

            mock_connector = MagicMock()
            with patch("aiohttp.TCPConnector", return_value=mock_connector), \
                 patch("aiohttp.ClientSession", side_effect=aiohttp.ClientError("network error")):
                result = await agent.request("hello", retries=2)
                assert result is None

    @pytest.mark.asyncio
    async def test_request_timeout_raises_after_retries(self):
        agent = GigaChatAgent()
        agent.set_config("cid", "csec")

        with patch.object(agent, "_get_access_token", new_callable=AsyncMock) as mock_token:
            mock_token.return_value = "access-token"

            mock_connector = MagicMock()
            with patch("aiohttp.TCPConnector", return_value=mock_connector), \
                 patch("aiohttp.ClientSession", side_effect=asyncio.TimeoutError()):
                with pytest.raises(asyncio.TimeoutError):
                    await agent.request("hello", retries=1)
