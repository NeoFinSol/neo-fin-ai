"""Unified AI service interface with automatic provider selection."""
import logging
from typing import Optional

from src.core.agent import agent as qwen_agent
from src.core.gigachat_agent import gigachat_agent
from src.models.settings import app_settings

logger = logging.getLogger(__name__)


class AIService:
    """
    Unified AI service that automatically selects the best available provider.
    
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
            
            # Configure GigaChat if not already configured
            if not self._agent._configured:
                self._agent.set_config(
                    client_id=app_settings.gigachat_client_id,
                    client_secret=app_settings.gigachat_client_secret,
                    auth_url=app_settings.gigachat_auth_url,
                    chat_url=app_settings.gigachat_chat_url,
                )
                logger.info("GigaChat AI service configured")
                
        elif app_settings.use_qwen:
            self._provider = "qwen"
            self._agent = qwen_agent
            
            # Configure Qwen if not already configured
            if not self._agent._configured:
                self._agent.set_config(
                    auth_token=app_settings.qwen_api_key,
                    url=app_settings.qwen_api_url,
                )
                logger.info("Qwen AI service configured")
                
        elif app_settings.use_local_llm:
            self._provider = "ollama"
            self._agent = None  # Will use direct HTTP calls
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
    
    async def invoke(self, input: dict, timeout: Optional[int] = None) -> Optional[str]:
        """
        Invoke AI service with automatic provider selection.

        Args:
            input: Input dictionary with tool_input and optional system prompt
            timeout: Request timeout in seconds

        Returns:
            Optional[str]: AI response or None
        """
        if not self.is_configured:
            logger.warning("AI service not configured - cannot invoke")
            return None

        if self._provider == "ollama":
            return await self._invoke_ollama(input, timeout)
        else:
            return await self._agent.invoke(input, timeout)

    async def invoke_with_retry(
        self,
        input: dict,
        timeout: Optional[int] = None,
        max_retries: int = 3,
        retry_delay: float = 1.0
    ) -> Optional[str]:
        """
        Invoke AI service with retry logic.

        Args:
            input: Input dictionary with tool_input and optional system prompt
            timeout: Request timeout in seconds
            max_retries: Maximum number of retry attempts
            retry_delay: Base delay between retries in seconds

        Returns:
            Optional[str]: AI response or None
        """
        import asyncio

        last_exception = None
        for attempt in range(max_retries):
            try:
                return await self.invoke(input, timeout)
            except asyncio.TimeoutError:
                # Don't retry timeout errors immediately
                if attempt < max_retries - 1:
                    delay = retry_delay * (2 ** attempt)  # Exponential backoff
                    logger.warning(
                        "AI request timeout (attempt %d/%d), retrying in %.2f seconds...",
                        attempt + 1, max_retries, delay
                    )
                    await asyncio.sleep(delay)
                else:
                    raise
            except Exception as e:
                last_exception = e
                if attempt < max_retries - 1:
                    delay = retry_delay * (2 ** attempt)
                    logger.warning(
                        "AI request error (attempt %d/%d): %s, retrying in %.2f seconds...",
                        attempt + 1, max_retries, str(e), delay
                    )
                    await asyncio.sleep(delay)
                else:
                    logger.error("AI request failed after all retries: %s", e)
                    raise

        return None
    
    async def _invoke_ollama(self, input: dict, timeout: Optional[int] = None) -> Optional[str]:
        """Invoke local Ollama LLM."""
        import aiohttp
        from aiohttp import ClientTimeout
        
        try:
            messages = input.get("tool_input", "")
            system = input.get("system")
            
            req_json = {
                "model": app_settings.llm_model or "llama3",
                "prompt": messages,
                "stream": False,
            }
            
            if system:
                req_json["system"] = system
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    app_settings.llm_url,
                    json=req_json,
                    timeout=ClientTimeout(total=timeout or 120)
                ) as response:
                    if response.status != 200:
                        logger.error("Ollama API error: %d", response.status)
                        return None
                    
                    result = await response.json()
                    return result.get("response", "")
                    
        except Exception as e:
            logger.exception("Error calling Ollama: %s", e)
            return None


# Global singleton instance
ai_service = AIService()
