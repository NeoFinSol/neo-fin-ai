import asyncio
import logging
from typing import Any, Optional

import aiohttp
from aiohttp import ClientTimeout

logger = logging.getLogger(__name__)


class AIAgentError(Exception):
    """Base class for AI agent errors."""

    pass


class ConfigurationError(AIAgentError):
    """Raised when agent is not properly configured."""

    pass


class AIAgentTimeoutError(AIAgentError):
    """Raised when AI agent request times out."""

    pass


class BaseAIAgent:
    """Base class for all AI agents with common functionality."""

    def __init__(self, timeout: int = 120):
        self.timeout = timeout
        self._configured: bool = False
        self._session: Optional[aiohttp.ClientSession] = None
        self.model: Optional[str] = None

    @property
    def is_configured(self) -> bool:
        """Return True when the agent has been successfully configured."""
        return self._configured

    def _ensure_configured(self) -> None:
        """Ensure agent is configured before making requests."""
        if not self._configured:
            raise ConfigurationError(f"{self.__class__.__name__} not configured.")

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create an aiohttp session."""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                timeout=ClientTimeout(total=self.timeout)
            )
        return self._session

    async def close(self) -> None:
        """Close the underlying aiohttp session."""
        if self._session and not self._session.closed:
            await self._session.close()
            logger.info("%s session closed", self.__class__.__name__)

    async def invoke(self, input: dict, timeout: Optional[int] = None) -> Optional[str]:
        """
        Unified invoke interface for all agents.

        Args:
            input: Input dictionary (context, prompts, etc.)
            timeout: Optional override for default timeout

        Returns:
            Optional[str]: Agent response or None
        """
        raise NotImplementedError("Subclasses must implement invoke()")
