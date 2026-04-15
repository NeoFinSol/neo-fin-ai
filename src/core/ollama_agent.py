"""
Ollama local LLM agent for NeoFin AI.

Implements the BaseAIAgent interface so that AIService can treat Ollama
identically to all other providers — no special-casing in the service layer.
"""

from __future__ import annotations

import logging
from typing import Optional

import aiohttp

from src.core.base_agent import BaseAIAgent
from src.models.settings import app_settings

logger = logging.getLogger(__name__)


def _build_ollama_payload(input: dict, model: str) -> dict:
    """Build the Ollama API request payload from a unified input dict."""
    prompt = input.get("prompt", "") or input.get("tool_input", "")
    if isinstance(prompt, dict):
        prompt = prompt.get("prompt", "")

    payload: dict = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        # Our pipelines expect the final content in `response`, not in
        # model-specific reasoning channels such as `thinking`.
        "think": input.get("think", False),
    }
    for key in ("system", "format", "options", "keep_alive"):
        if input.get(key) is not None:
            payload[key] = input[key]
    return payload


class OllamaAgent(BaseAIAgent):
    """Agent for invoking a local LLM via the Ollama HTTP API.

    Uses a shared aiohttp.ClientSession (inherited from BaseAIAgent._get_session)
    to avoid per-call TCP handshake overhead.
    """

    def __init__(self, timeout: int = 120) -> None:
        super().__init__(timeout=timeout)
        # Mark as always configured — Ollama is available when the URL is set.
        self._configured = True
        # Override the base model attribute with Ollama default
        self.model = app_settings.llm_model or "llama3"

    @property
    def url(self) -> str:
        return app_settings.llm_url or "http://localhost:11434/api/generate"

    def _effective_model(self) -> str:
        return app_settings.llm_model or "llama3"

    async def invoke(self, input: dict, timeout: Optional[int] = None) -> Optional[str]:
        """Invoke the local Ollama model and return the generated text."""
        payload = _build_ollama_payload(input, self._effective_model())
        actual_timeout = aiohttp.ClientTimeout(total=timeout or self.timeout)

        try:
            session = await self._get_session()
            async with session.post(
                self.url, json=payload, timeout=actual_timeout
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    return data.get("response", "")
                logger.error("Ollama returned status %s", response.status)
                return None
        except Exception as exc:
            logger.error("Ollama invocation failed: %s", exc)
            return None


# Module-level singleton — registered by AIService._configure()
ollama_agent = OllamaAgent()
