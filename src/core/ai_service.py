"""Unified AI service interface with automatic provider selection."""

import asyncio
import os
import time
from typing import Any, Literal, Optional

from src.core.agent import agent as qwen_agent
from src.core.gigachat_agent import gigachat_agent
from src.core.huggingface_agent import huggingface_agent
from src.core.ollama_agent import ollama_agent
from src.models.settings import app_settings
from src.utils.circuit_breaker import CircuitBreaker, CircuitBreakerOpenError
from src.utils.logging_config import get_logger, metrics
from src.utils.retry_utils import retry_with_timeout

logger = get_logger(__name__)

# Configuration from environment
AI_TIMEOUT = int(os.getenv("AI_TIMEOUT", "120"))
AI_RETRY_COUNT = int(os.getenv("AI_RETRY_COUNT", "2"))
AI_RETRY_BACKOFF = float(os.getenv("AI_RETRY_BACKOFF", "2.0"))

SUPPORTED_AI_PROVIDERS = ("gigachat", "huggingface", "qwen", "ollama")
AIProviderName = Literal["gigachat", "huggingface", "qwen", "ollama"]
_TIMEOUT_RETRY_EXHAUSTED = object()


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
        self._default_provider: Optional[AIProviderName] = None
        self._providers: dict[AIProviderName, Any] = {}
        self._circuit_breakers: dict[AIProviderName, CircuitBreaker] = {}
        self._configure()

    @staticmethod
    def normalize_requested_provider(
        provider: str | None,
    ) -> Optional[AIProviderName]:
        """Normalize optional request-level provider selection."""
        if provider is None:
            return None

        value = str(provider).strip().lower()
        if not value or value == "auto":
            return None
        if value not in SUPPORTED_AI_PROVIDERS:
            raise ValueError(f"Unsupported AI provider: {provider}")
        return value  # type: ignore[return-value]

    def _register_provider(self, provider: AIProviderName, agent: Any) -> None:
        self._providers[provider] = agent
        self._circuit_breakers[provider] = CircuitBreaker(
            name=f"AI Service [{provider}]",
        )
        if self._default_provider is None:
            self._default_provider = provider

    def _resolve_provider(
        self,
        requested_provider: str | None = None,
    ) -> Optional[AIProviderName]:
        try:
            normalized = self.normalize_requested_provider(requested_provider)
        except ValueError:
            return None

        if normalized is None:
            return self._default_provider
        if normalized not in self._providers:
            return None
        return normalized

    def _configure(self):
        """Configure the AI service based on available credentials."""
        self._default_provider = None
        self._providers = {}
        self._circuit_breakers = {}

        if app_settings.use_gigachat:
            if not gigachat_agent.is_configured:
                gigachat_agent.set_config(
                    client_id=app_settings.gigachat_client_id,
                    client_secret=app_settings.gigachat_client_secret,
                    auth_url=app_settings.gigachat_auth_url,
                    chat_url=app_settings.gigachat_chat_url,
                )
            self._register_provider("gigachat", gigachat_agent)
            logger.info("GigaChat AI service configured")

        if app_settings.use_huggingface:
            if not huggingface_agent.is_configured:
                huggingface_agent.set_config(
                    token=app_settings.hf_token,
                    model=app_settings.hf_model,
                )
            self._register_provider("huggingface", huggingface_agent)
            logger.info(
                "Hugging Face AI service configured with model: %s",
                app_settings.hf_model,
            )

        if app_settings.use_qwen:
            if not qwen_agent.is_configured:
                qwen_agent.set_config(
                    auth_token=app_settings.qwen_api_key,
                    url=app_settings.qwen_api_url,
                )
            self._register_provider("qwen", qwen_agent)
            logger.info("Qwen AI service configured")

        if app_settings.use_local_llm:
            self._register_provider("ollama", ollama_agent)
            logger.info("Local LLM (Ollama) will be used")

        if not self._providers:
            logger.warning("No AI service configured - NLP features will be disabled")

    @property
    def provider(self) -> Optional[str]:
        """Get current AI provider name."""
        return self._default_provider

    @property
    def is_configured(self) -> bool:
        """Check if any AI service is configured."""
        return self._default_provider is not None

    @property
    def is_available(self) -> bool:
        """Check if AI service is available (configured and circuit breaker closed)."""
        return self.is_provider_available(self._default_provider)

    @property
    def available_providers(self) -> list[str]:
        """List configured AI providers in priority order."""
        return list(self._providers.keys())

    def is_provider_available(self, provider: str | None) -> bool:
        """Check if a specific provider is configured and not circuit-open."""
        resolved_provider = self._resolve_provider(provider)
        if resolved_provider is None:
            return False
        breaker = self._circuit_breakers.get(resolved_provider)
        return breaker is not None and breaker.is_available

    def get_circuit_breaker_status(self, provider: str | None = None) -> dict:
        """Get AI circuit breaker status."""
        resolved_provider = self._resolve_provider(provider)
        if resolved_provider is None:
            return {}
        return self._circuit_breakers[resolved_provider].get_status()

    async def close(self) -> None:
        """Close provider-specific runtime resources such as shared HTTP sessions."""
        seen_agents: set[int] = set()
        for agent in self._providers.values():
            if agent is None:
                continue
            agent_id = id(agent)
            if agent_id in seen_agents:
                continue
            seen_agents.add(agent_id)

            close_method = getattr(agent, "close", None)
            if close_method is None:
                continue

            await close_method()

    async def _invoke_with_provider(
        self,
        provider: AIProviderName,
        input: dict,
        timeout: Optional[int],
    ) -> Optional[str]:
        agent = self._providers[provider]
        return await agent.invoke(input, timeout=timeout)

    async def _handle_retry_timeout_exhaustion(
        self,
        breaker: CircuitBreaker,
        resolved_provider: AIProviderName,
        actual_timeout: int,
        start_time: float,
    ) -> None:
        duration_ms = (time.monotonic() - start_time) * 1000
        logger.warning(
            "AI invocation timed out after retries (provider=%s, timeout=%ds)",
            resolved_provider,
            actual_timeout,
            extra={"duration_ms": duration_ms},
        )
        await breaker.record_failure()
        metrics.record_ai_failure()

    async def invoke(
        self,
        input: dict,
        timeout: Optional[int] = None,
        use_retry: bool = True,
        provider: str | None = None,
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

        resolved_provider = self._resolve_provider(provider)

        if resolved_provider is None:
            if not self.is_configured:
                logger.warning("AI service not configured - skipping invocation")
            else:
                logger.warning(
                    "Requested AI provider is unavailable: %s",
                    provider,
                )
            return None

        breaker = self._circuit_breakers[resolved_provider]

        # Check circuit breaker
        if not breaker.is_available:
            retry_after = breaker.time_until_retry
            logger.warning(
                "AI provider temporarily disabled (provider=%s, retry_after=%ds)",
                resolved_provider,
                retry_after,
                extra={"extra_data": {"retry_after": retry_after}},
            )
            metrics.record_ai_failure()
            return None

        start_time = time.monotonic()
        logger.info("AI invocation started (provider: %s)", resolved_provider)

        try:
            # Define the operation
            async def ai_operation():
                return await self._invoke_with_provider(
                    resolved_provider,
                    input,
                    timeout=actual_timeout,
                )

            # Execute with or without retry
            if use_retry and AI_RETRY_COUNT > 0:
                result = await retry_with_timeout(
                    ai_operation,
                    timeout=actual_timeout,
                    max_retries=AI_RETRY_COUNT,
                    backoff_multiplier=AI_RETRY_BACKOFF,
                    fallback=lambda: _TIMEOUT_RETRY_EXHAUSTED,
                    operation_name=f"AI invocation ({resolved_provider})",
                )
            else:
                result = await asyncio.wait_for(ai_operation(), timeout=actual_timeout)

            if result is _TIMEOUT_RETRY_EXHAUSTED:
                await self._handle_retry_timeout_exhaustion(
                    breaker,
                    resolved_provider,
                    actual_timeout,
                    start_time,
                )
                return None

            # Success
            duration_ms = (time.monotonic() - start_time) * 1000
            logger.info("AI invocation completed", extra={"duration_ms": duration_ms})
            await breaker.record_success()
            return result

        except asyncio.TimeoutError:
            duration_ms = (time.monotonic() - start_time) * 1000
            logger.warning(
                "AI invocation timed out after %ds",
                actual_timeout,
                extra={"duration_ms": duration_ms},
            )
            await breaker.record_failure()
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
            await breaker.record_failure()
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

        New code should use invoke(use_retry=True) directly.
        max_retries and retry_delay are accepted but ignored — retry behaviour
        is controlled by AI_RETRY_COUNT and AI_RETRY_BACKOFF env vars.
        """
        return await self.invoke(input=input, timeout=timeout, use_retry=True)


# Global AI service instance
ai_service = AIService()
