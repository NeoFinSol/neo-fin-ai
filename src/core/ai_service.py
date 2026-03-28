"""Unified AI service interface with automatic provider selection."""

import asyncio
import logging
import os
import time
from typing import Optional

from src.core.agent import agent as qwen_agent
from src.core.gigachat_agent import gigachat_agent
from src.core.huggingface_agent import huggingface_agent
from src.models.settings import app_settings
from src.utils.circuit_breaker import ai_circuit_breaker, CircuitBreakerOpenError
from src.utils.logging_config import get_logger, metrics
from src.utils.retry_utils import retry_with_timeout

logger = get_logger(__name__)

# Configuration from environment
AI_TIMEOUT = int(os.getenv("AI_TIMEOUT", "120"))
AI_RETRY_COUNT = int(os.getenv("AI_RETRY_COUNT", "2"))
AI_RETRY_BACKOFF = float(os.getenv("AI_RETRY_BACKOFF", "2.0"))


class AIService:
    """
    Unified AI service with resilience patterns:
    - Circuit breaker (prevents cascading failures)
    - Retry with exponential backoff (handles transient failures)
    - Timeout control (prevents hanging)
    - Graceful degradation (returns None instead of crashing)
    
    Priority order:
    1. GigaChat (if configured)
    2. Qwen (if configured)
    3. Local LLM via Ollama (if configured)
    """

    def __init__(self):
        self._provider = None
        self._agent = None
        self._configure()

    def _configure(self):
        """Configure the AI service based on available credentials."""
        if app_settings.use_gigachat:
            self._provider = "gigachat"
            self._agent = gigachat_agent

            if not self._agent._configured:
                self._agent.set_config(
                    client_id=app_settings.gigachat_client_id,
                    client_secret=app_settings.gigachat_client_secret,
                    auth_url=app_settings.gigachat_auth_url,
                    chat_url=app_settings.gigachat_chat_url,
                )
                logger.info("GigaChat AI service configured")

        elif app_settings.use_huggingface:
            self._provider = "huggingface"
            self._agent = huggingface_agent

            if not self._agent._configured:
                self._agent.set_config(
                    token=app_settings.hf_token,
                    model=app_settings.hf_model,
                )
                logger.info(
                    "Hugging Face AI service configured with model: %s",
                    app_settings.hf_model,
                )

        elif app_settings.use_qwen:
            self._provider = "qwen"
            self._agent = qwen_agent

            if not self._agent._configured:
                self._agent.set_config(
                    auth_token=app_settings.qwen_api_key,
                    url=app_settings.qwen_api_url,
                )
                logger.info("Qwen AI service configured")

        elif app_settings.use_local_llm:
            self._provider = "ollama"
            self._agent = None
            logger.info("Local LLM (Ollama) will be used")

        else:
            self._provider = None
            self._agent = None
            logger.warning("No AI service configured - NLP features will be disabled")

    @property
    def provider(self) -> Optional[str]:
        """Get current AI provider name."""
        return self._provider

    @property
    def is_configured(self) -> bool:
        """Check if any AI service is configured."""
        return self._provider is not None

    @property
    def is_available(self) -> bool:
        """Check if AI service is available (configured and circuit breaker closed)."""
        return self.is_configured and ai_circuit_breaker.is_available

    def get_circuit_breaker_status(self) -> dict:
        """Get AI circuit breaker status."""
        return ai_circuit_breaker.get_status()

    async def close(self) -> None:
        """Close provider-specific runtime resources such as shared HTTP sessions."""
        if self._agent is None:
            return

        close_method = getattr(self._agent, "close", None)
        if close_method is None:
            return

        await close_method()

    async def invoke(
        self,
        input: dict,
        timeout: Optional[int] = None,
        use_retry: bool = True,
    ) -> Optional[str]:
        """
        Invoke AI service with resilience patterns.
        
        Features:
        - Circuit breaker (blocks requests if service is failing)
        - Retry with exponential backoff (handles transient failures)
        - Timeout control (prevents hanging)
        - Graceful degradation (returns None on failure)

        Args:
            input: Input dictionary with tool_input and optional system prompt
            timeout: Request timeout in seconds (default: AI_TIMEOUT env)
            use_retry: Enable retry logic (default: True)

        Returns:
            Optional[str]: AI response or None (on failure/timeout/circuit open)
        """
        actual_timeout = timeout or AI_TIMEOUT
        
        # Check if AI is configured
        if not self.is_configured:
            logger.warning("AI service not configured - skipping invocation")
            return None
        
        # Check circuit breaker
        if not ai_circuit_breaker.is_available:
            retry_after = ai_circuit_breaker.time_until_retry
            logger.warning(
                "AI service temporarily disabled (circuit breaker open). Retry after %ds",
                retry_after,
                extra={"extra_data": {"retry_after": retry_after}},
            )
            metrics.record_ai_failure()
            return None

        start_time = time.monotonic()
        logger.info("AI invocation started (provider: %s)", self._provider)

        try:
            # Define the operation
            async def ai_operation():
                if self._provider == "ollama":
                    return await self._invoke_ollama(input, timeout=actual_timeout)
                else:
                    return await self._agent.invoke(input, timeout=actual_timeout)
            
            # Execute with or without retry
            if use_retry and AI_RETRY_COUNT > 0:
                result = await retry_with_timeout(
                    ai_operation,
                    timeout=actual_timeout,
                    max_retries=AI_RETRY_COUNT,
                    backoff_multiplier=AI_RETRY_BACKOFF,
                    fallback=lambda: None,
                    operation_name=f"AI invocation ({self._provider})",
                )
            else:
                result = await asyncio.wait_for(ai_operation(), timeout=actual_timeout)
            
            # Success
            duration_ms = (time.monotonic() - start_time) * 1000
            logger.info("AI invocation completed", extra={"duration_ms": duration_ms})
            await ai_circuit_breaker.record_success()
            return result

        except asyncio.TimeoutError:
            duration_ms = (time.monotonic() - start_time) * 1000
            logger.warning(
                "AI invocation timed out after %ds",
                actual_timeout,
                extra={"duration_ms": duration_ms},
            )
            await ai_circuit_breaker.record_failure()
            metrics.record_ai_failure()
            return None

        except CircuitBreakerOpenError:
            # Should not happen since we check is_available above, but handle anyway
            logger.warning("AI invocation blocked by circuit breaker")
            metrics.record_ai_failure()
            return None

        except Exception as exc:
            duration_ms = (time.monotonic() - start_time) * 1000
            logger.error(
                "AI invocation failed: %s",
                exc,
                exc_info=True,
                extra={"duration_ms": duration_ms},
            )
            await ai_circuit_breaker.record_failure()
            metrics.record_ai_failure()
            return None  # Graceful degradation

    async def invoke_with_retry(
        self,
        input: dict,
        timeout: Optional[int] = None,
        max_retries: Optional[int] = None,
        retry_delay: Optional[float] = None,
    ) -> Optional[str]:
        """
        Legacy wrapper for invoke(use_retry=True) for backward compatibility.

        This method exists for compatibility with tests and legacy code.
        New code should use invoke(use_retry=True) directly.

        Args:
            input: Input dictionary with tool_input and optional system prompt
            timeout: Request timeout in seconds (default: AI_TIMEOUT env)
            max_retries: Ignored (uses AI_RETRY_COUNT from env)
            retry_delay: Ignored (uses AI_RETRY_BACKOFF from env)

        Returns:
            Optional[str]: AI response or None (on failure/timeout/circuit open)
        """
        # Ignore max_retries and retry_delay for now (use env vars)
        return await self.invoke(input=input, timeout=timeout, use_retry=True)

    async def _invoke_ollama(
        self,
        input: dict,
        timeout: Optional[int] = None,
    ) -> Optional[str]:
        """
        Invoke local LLM via Ollama HTTP API.
        
        Args:
            input: Input dictionary with prompt
            timeout: Request timeout in seconds
        
        Returns:
            Optional[str]: Generated text or None
        """
        import aiohttp
        
        url = os.getenv("LLM_URL", "http://localhost:11434/api/generate")
        model = os.getenv("LLM_MODEL", "llama3")
        
        prompt = input.get("prompt", "") or input.get("tool_input", "")
        # Handle case where tool_input might be a dict with prompt key
        if isinstance(prompt, dict):
            prompt = prompt.get("prompt", "")
        
        payload = {
            "model": model,
            "prompt": prompt,
            "stream": False,
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload, timeout=timeout) as response:
                    if response.status == 200:
                        data = await response.json()
                        return data.get("response", "")
                    else:
                        logger.error("Ollama returned status %s", response.status)
                        return None
        except Exception as exc:
            logger.error("Ollama invocation failed: %s", exc)
            return None


# Global AI service instance
ai_service = AIService()
