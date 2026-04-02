import logging
from typing import Optional

import aiohttp

from src.core.base_agent import BaseAIAgent

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 120
MAX_RETRIES = 3


class HuggingFaceAgent(BaseAIAgent):
    """Agent for interacting with Hugging Face Inference API."""

    def __init__(self, timeout: int = DEFAULT_TIMEOUT):
        super().__init__(timeout=timeout)
        self._token: Optional[str] = None
        self._model: str = "Qwen/Qwen3.5-9B-Instruct"
        self._base_url: str = "https://router.huggingface.co/v1"

    def set_config(
        self,
        token: str,
        model: str = "Qwen/Qwen3.5-9B-Instruct",
    ) -> None:
        """Configure agent with Hugging Face credentials."""
        if not token or not token.strip():
            raise ValueError("Hugging Face token is required")

        self._token = token.strip()
        self._model = model.strip()
        self._configured = True
        logger.info("Hugging Face agent configured with model: %s", self._model)

    def _ensure_configured(self) -> None:
        """Ensure agent is configured."""
        if not self._configured or not self._token:
            raise ValueError(
                "Hugging Face agent not configured. Call set_config(token) first"
            )

    async def invoke(self, input: dict, timeout: Optional[int] = None) -> Optional[str]:
        """Invoke the model with input text."""
        self._ensure_configured()

        tool_input = input.get("tool_input", "")
        system = input.get("system")

        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": tool_input})

        payload = {
            "model": self._model,
            "messages": messages,
            "max_tokens": 2048,
            "temperature": 0.7,
        }

        headers = {
            "Authorization": f"Bearer {self._token}",
            "Content-Type": "application/json",
        }

        url = f"{self._base_url}/chat/completions"

        try:
            session = await self._get_session()
            async with session.post(
                url,
                json=payload,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=timeout or self.timeout),
            ) as response:
                if response.status != 200:
                    error_text = await response.text()
                    logger.error("HF API error %d: %s", response.status, error_text)
                    return None

                result = await response.json()
                return (
                    result.get("choices", [{}])[0].get("message", {}).get("content", "")
                )

        except Exception as e:
            logger.exception("HF API request failed: %s", e)
            return None


# Global singleton
huggingface_agent = HuggingFaceAgent()
