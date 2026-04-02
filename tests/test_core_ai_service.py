"""Tests for core/ai_service.py — unified AI service."""
import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.core.ai_service import AIService


class TestAIServiceInit:
    """Tests for AIService initialization and provider selection."""

    def test_no_provider_when_nothing_configured(self):
        with patch("src.core.ai_service.app_settings") as mock_settings:
            mock_settings.use_gigachat = False
            mock_settings.use_huggingface = False
            mock_settings.use_qwen = False
            mock_settings.use_local_llm = False
            svc = AIService()
            assert svc.provider is None
            assert svc.is_configured is False

    def test_gigachat_provider_selected_first(self):
        with patch("src.core.ai_service.app_settings") as mock_settings, \
             patch("src.core.ai_service.gigachat_agent") as mock_gc:
            mock_settings.use_gigachat = True
            mock_settings.use_huggingface = False
            mock_settings.use_qwen = False
            mock_settings.use_local_llm = False
            mock_gc._configured = True
            svc = AIService()
            assert svc.provider == "gigachat"
            assert svc.is_configured is True

    def test_gigachat_configured_if_not_already(self):
        with patch("src.core.ai_service.app_settings") as mock_settings, \
             patch("src.core.ai_service.gigachat_agent") as mock_gc:
            mock_settings.use_gigachat = True
            mock_settings.use_huggingface = False
            mock_settings.use_qwen = False
            mock_settings.use_local_llm = False
            mock_settings.gigachat_client_id = "cid"
            mock_settings.gigachat_client_secret = "csec"
            mock_settings.gigachat_auth_url = "https://auth.url"
            mock_settings.gigachat_chat_url = "https://chat.url"
            mock_gc._configured = False
            svc = AIService()
            mock_gc.set_config.assert_called_once()

    def test_huggingface_provider_selected(self):
        with patch("src.core.ai_service.app_settings") as mock_settings, \
             patch("src.core.ai_service.huggingface_agent") as mock_hf:
            mock_settings.use_gigachat = False
            mock_settings.use_huggingface = True
            mock_settings.use_qwen = False
            mock_settings.use_local_llm = False
            mock_hf._configured = True
            svc = AIService()
            assert svc.provider == "huggingface"

    def test_qwen_provider_selected(self):
        with patch("src.core.ai_service.app_settings") as mock_settings, \
             patch("src.core.ai_service.qwen_agent") as mock_qwen:
            mock_settings.use_gigachat = False
            mock_settings.use_huggingface = False
            mock_settings.use_qwen = True
            mock_settings.use_local_llm = False
            mock_qwen._configured = True
            svc = AIService()
            assert svc.provider == "qwen"

    def test_ollama_provider_selected(self):
        with patch("src.core.ai_service.app_settings") as mock_settings:
            mock_settings.use_gigachat = False
            mock_settings.use_huggingface = False
            mock_settings.use_qwen = False
            mock_settings.use_local_llm = True
            svc = AIService()
            assert svc.provider == "ollama"
            assert svc.is_configured is True


class TestAIServiceInvoke:
    """Tests for AIService.invoke method."""

    @pytest.mark.asyncio
    async def test_invoke_not_configured_returns_none(self):
        with patch("src.core.ai_service.app_settings") as mock_settings:
            mock_settings.use_gigachat = False
            mock_settings.use_huggingface = False
            mock_settings.use_qwen = False
            mock_settings.use_local_llm = False
            svc = AIService()
            result = await svc.invoke({"tool_input": "test"})
            assert result is None

    @pytest.mark.asyncio
    async def test_invoke_delegates_to_agent(self):
        with patch("src.core.ai_service.app_settings") as mock_settings, \
             patch("src.core.ai_service.qwen_agent") as mock_agent:
            mock_settings.use_gigachat = False
            mock_settings.use_huggingface = False
            mock_settings.use_qwen = True
            mock_settings.use_local_llm = False
            mock_agent._configured = True
            mock_agent.invoke = AsyncMock(return_value="response text")
            svc = AIService()
            result = await svc.invoke({"tool_input": "hello"})
            assert result == "response text"

    @pytest.mark.asyncio
    async def test_invoke_ollama_path(self):
        with patch("src.core.ai_service.app_settings") as mock_settings:
            mock_settings.use_gigachat = False
            mock_settings.use_huggingface = False
            mock_settings.use_qwen = False
            mock_settings.use_local_llm = True
            svc = AIService()
            with patch.object(svc, "_invoke_ollama", new_callable=AsyncMock) as mock_ollama:
                mock_ollama.return_value = "ollama response"
                result = await svc.invoke({"tool_input": "test"})
                assert result == "ollama response"
                mock_ollama.assert_called_once()

    @pytest.mark.asyncio
    async def test_invoke_uses_requested_provider_override(self):
        with patch("src.core.ai_service.app_settings") as mock_settings, \
             patch("src.core.ai_service.gigachat_agent") as mock_gc:
            mock_settings.use_gigachat = True
            mock_settings.use_huggingface = False
            mock_settings.use_qwen = False
            mock_settings.use_local_llm = True
            mock_settings.gigachat_client_id = "cid"
            mock_settings.gigachat_client_secret = "csec"
            mock_settings.gigachat_auth_url = "https://auth.url"
            mock_settings.gigachat_chat_url = "https://chat.url"
            mock_gc._configured = True
            mock_gc.invoke = AsyncMock(return_value="gigachat response")
            svc = AIService()

            with patch.object(svc, "_invoke_ollama", new_callable=AsyncMock) as mock_ollama:
                mock_ollama.return_value = "ollama response"
                result = await svc.invoke({"tool_input": "test"}, provider="ollama")

            assert result == "ollama response"
            mock_ollama.assert_awaited_once()
            mock_gc.invoke.assert_not_awaited()


class TestAIServiceInvokeWithRetry:
    """Tests for AIService.invoke_with_retry method."""

    @pytest.mark.asyncio
    async def test_returns_on_first_success(self):
        with patch("src.core.ai_service.app_settings") as mock_settings, \
             patch("src.core.ai_service.qwen_agent") as mock_agent:
            mock_settings.use_gigachat = False
            mock_settings.use_huggingface = False
            mock_settings.use_qwen = True
            mock_settings.use_local_llm = False
            mock_agent._configured = True
            mock_agent.invoke = AsyncMock(return_value="ok")
            svc = AIService()
            result = await svc.invoke_with_retry({"tool_input": "test"}, max_retries=3)
            assert result == "ok"

    @pytest.mark.asyncio
    async def test_retries_on_timeout_then_raises(self):
        """Test that invoke returns None after retries on timeout (graceful degradation)."""
        with patch("src.core.ai_service.app_settings") as mock_settings, \
             patch("src.core.ai_service.qwen_agent") as mock_agent:
            mock_settings.use_gigachat = False
            mock_settings.use_huggingface = False
            mock_settings.use_qwen = True
            mock_settings.use_local_llm = False
            mock_agent._configured = True
            mock_agent.invoke = AsyncMock(side_effect=asyncio.TimeoutError())
            svc = AIService()
            # New behavior: returns None instead of raising (graceful degradation)
            result = await svc.invoke_with_retry(
                {"tool_input": "test"}, max_retries=2, retry_delay=0.01
            )
            assert result is None

    @pytest.mark.asyncio
    async def test_retries_on_exception_then_raises(self):
        """Test that invoke returns None after retries on exception (graceful degradation)."""
        with patch("src.core.ai_service.app_settings") as mock_settings, \
             patch("src.core.ai_service.qwen_agent") as mock_agent:
            mock_settings.use_gigachat = False
            mock_settings.use_huggingface = False
            mock_settings.use_qwen = True
            mock_settings.use_local_llm = False
            mock_agent._configured = True
            mock_agent.invoke = AsyncMock(side_effect=RuntimeError("boom"))
            svc = AIService()
            # New behavior: returns None instead of raising (graceful degradation)
            result = await svc.invoke_with_retry(
                {"tool_input": "test"}, max_retries=2, retry_delay=0.01
            )
            assert result is None

    @pytest.mark.asyncio
    async def test_succeeds_on_second_attempt(self):
        with patch("src.core.ai_service.app_settings") as mock_settings, \
             patch("src.core.ai_service.qwen_agent") as mock_agent:
            mock_settings.use_gigachat = False
            mock_settings.use_huggingface = False
            mock_settings.use_qwen = True
            mock_settings.use_local_llm = False
            mock_agent._configured = True
            mock_agent.invoke = AsyncMock(
                side_effect=[RuntimeError("first fail"), "success"]
            )
            svc = AIService()
            result = await svc.invoke_with_retry(
                {"tool_input": "test"}, max_retries=3, retry_delay=0.01
            )
            assert result == "success"


class TestAIServiceInvokeOllama:
    """Tests for AIService._invoke_ollama method."""

    @pytest.mark.asyncio
    async def test_ollama_success(self):
        import aiohttp
        with patch("src.core.ai_service.app_settings") as mock_settings:
            mock_settings.use_gigachat = False
            mock_settings.use_huggingface = False
            mock_settings.use_qwen = False
            mock_settings.use_local_llm = True
            mock_settings.llm_model = "llama3"
            mock_settings.llm_url = "http://localhost:11434/api/generate"
            svc = AIService()

            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.json = AsyncMock(return_value={"response": "ollama says hi"})
            mock_response.__aenter__ = AsyncMock(return_value=mock_response)
            mock_response.__aexit__ = AsyncMock(return_value=False)

            mock_session = AsyncMock()
            mock_session.post = MagicMock(return_value=mock_response)
            mock_session.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session.__aexit__ = AsyncMock(return_value=False)

            with patch("aiohttp.ClientSession", return_value=mock_session):
                result = await svc._invoke_ollama({"tool_input": "hello"})
                assert result == "ollama says hi"

    @pytest.mark.asyncio
    async def test_ollama_non_200_returns_none(self):
        with patch("src.core.ai_service.app_settings") as mock_settings:
            mock_settings.use_gigachat = False
            mock_settings.use_huggingface = False
            mock_settings.use_qwen = False
            mock_settings.use_local_llm = True
            mock_settings.llm_model = "llama3"
            mock_settings.llm_url = "http://localhost:11434/api/generate"
            svc = AIService()

            mock_response = AsyncMock()
            mock_response.status = 500
            mock_response.__aenter__ = AsyncMock(return_value=mock_response)
            mock_response.__aexit__ = AsyncMock(return_value=False)

            mock_session = AsyncMock()
            mock_session.post = MagicMock(return_value=mock_response)
            mock_session.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session.__aexit__ = AsyncMock(return_value=False)

            with patch("aiohttp.ClientSession", return_value=mock_session):
                result = await svc._invoke_ollama({"tool_input": "hello"})
                assert result is None

    @pytest.mark.asyncio
    async def test_ollama_exception_returns_none(self):
        with patch("src.core.ai_service.app_settings") as mock_settings:
            mock_settings.use_gigachat = False
            mock_settings.use_huggingface = False
            mock_settings.use_qwen = False
            mock_settings.use_local_llm = True
            mock_settings.llm_model = "llama3"
            mock_settings.llm_url = "http://localhost:11434/api/generate"
            svc = AIService()

            with patch("aiohttp.ClientSession", side_effect=Exception("connection refused")):
                result = await svc._invoke_ollama({"tool_input": "hello"})
                assert result is None

    @pytest.mark.asyncio
    async def test_ollama_forwards_system_prompt_and_format(self):
        with patch("src.core.ai_service.app_settings") as mock_settings:
            mock_settings.use_gigachat = False
            mock_settings.use_huggingface = False
            mock_settings.use_qwen = False
            mock_settings.use_local_llm = True
            mock_settings.llm_model = "qwen3:8b"
            mock_settings.llm_url = "http://localhost:11434/api/generate"
            svc = AIService()

            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.json = AsyncMock(return_value={"response": "{\"ok\": true}"})
            mock_response.__aenter__ = AsyncMock(return_value=mock_response)
            mock_response.__aexit__ = AsyncMock(return_value=False)

            mock_session = AsyncMock()
            mock_session.post = MagicMock(return_value=mock_response)
            mock_session.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session.__aexit__ = AsyncMock(return_value=False)

            with patch("aiohttp.ClientSession", return_value=mock_session):
                result = await svc._invoke_ollama(
                    {
                        "tool_input": "return a JSON object",
                        "system": "Reply only with valid JSON.",
                        "format": "json",
                    }
                )

            assert result == "{\"ok\": true}"
            _, kwargs = mock_session.post.call_args
            assert kwargs["json"]["system"] == "Reply only with valid JSON."
            assert kwargs["json"]["format"] == "json"

    @pytest.mark.asyncio
    async def test_ollama_disables_thinking_by_default(self):
        with patch("src.core.ai_service.app_settings") as mock_settings:
            mock_settings.use_gigachat = False
            mock_settings.use_huggingface = False
            mock_settings.use_qwen = False
            mock_settings.use_local_llm = True
            mock_settings.llm_model = "qwen3.5:9b"
            mock_settings.llm_url = "http://localhost:11434/api/generate"
            svc = AIService()

            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.json = AsyncMock(return_value={"response": "{\"ok\": true}"})
            mock_response.__aenter__ = AsyncMock(return_value=mock_response)
            mock_response.__aexit__ = AsyncMock(return_value=False)

            mock_session = AsyncMock()
            mock_session.post = MagicMock(return_value=mock_response)
            mock_session.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session.__aexit__ = AsyncMock(return_value=False)

            with patch("aiohttp.ClientSession", return_value=mock_session):
                await svc._invoke_ollama({"tool_input": "return JSON"})

            _, kwargs = mock_session.post.call_args
            assert kwargs["json"]["think"] is False
