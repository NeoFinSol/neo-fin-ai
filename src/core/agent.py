import asyncio
import logging
from typing import Optional

import aiohttp
from aiohttp import ClientError, ClientTimeout, ContentTypeError

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 120  # seconds
MAX_RETRIES = 3
RETRY_DELAY = 1.0  # seconds
RETRY_BACKOFF = 2.0  # multiplier


class ConfigurationError(Exception):
    """Raised when agent is not properly configured."""
    pass


class Agent:
    def __init__(self, timeout: int = DEFAULT_TIMEOUT):
        self._auth_token: Optional[str] = None
        self._url: Optional[str] = None
        self.model: str = "qwen3.5-plus"
        self.timeout = timeout
        self._configured: bool = False

    def set_config(self, auth_token: Optional[str], url: Optional[str]) -> None:
        """
        Configure agent with API credentials.
        
        Args:
            auth_token: Qwen API authentication token
            url: Qwen API base URL
            
        Raises:
            ConfigurationError: If URL or auth_token is missing or empty
        """
        if not auth_token or not auth_token.strip():
            raise ConfigurationError("Qwen API auth token is required")
        
        if not url or not url.strip():
            raise ConfigurationError("Qwen API URL is required")
        
        self._auth_token = auth_token.strip()
        self._url = url.strip().rstrip('/')
        self._configured = True
        logger.info("Agent configured with URL: %s", self._url)

    def _ensure_configured(self) -> None:
        """Ensure agent is configured before making requests."""
        if not self._configured or not self._url or not self._auth_token:
            raise ConfigurationError(
                "Agent not configured. Call set_config(auth_token, url) first"
            )

    async def invoke(self, input: dict, timeout: Optional[int] = None) -> Optional[str]:
        """
        Invoke the agent with timeout support.
        
        Args:
            input: Input dictionary with chat_id and tool_input
            timeout: Request timeout in seconds
            
        Returns:
            Optional[str]: Agent response or None
            
        Raises:
            asyncio.TimeoutError: If request times out
            ConfigurationError: If agent is not configured
        """
        self._ensure_configured()
        
        actual_timeout = timeout or self.timeout
        try:
            async with asyncio.timeout(actual_timeout):
                return await self.request(
                    chat_id=input.get("chat_id", "default"),
                    message=input.get("tool_input", ""),
                )
        except asyncio.TimeoutError:
            logger.error("Agent request timeout after %d seconds", actual_timeout)
            raise

    async def request(
        self, 
        chat_id: str, 
        message: str, 
        *, 
        parent_id: Optional[str] = None, 
        system: Optional[str] = None,
        timeout: Optional[int] = None,
        retries: int = MAX_RETRIES,
    ) -> Optional[str]:
        """
        Send request to Qwen API with retry logic.
        
        Args:
            chat_id: Chat identifier
            message: Message to send
            parent_id: Optional parent message ID
            system: Optional system prompt
            timeout: Request timeout in seconds
            retries: Number of retry attempts
            
        Returns:
            Optional[str]: API response or None
            
        Raises:
            ConfigurationError: If agent is not configured
        """
        self._ensure_configured()

        headers = {
            "Authorization": f"Bearer {self._auth_token}",
            "Content-Type": "application/json"
        }

        req_json = {
            "model": self.model,
            "message": message,
            "chat_id": chat_id
        }

        if system is not None:
            req_json["system"] = system
        if parent_id is not None:
            req_json["parent_id"] = parent_id

        actual_timeout = timeout or self.timeout
        last_exception: Optional[Exception] = None
        
        for attempt in range(retries):
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.post(
                        f"{self._url}/chat",
                        json=req_json,
                        headers=headers,
                        timeout=ClientTimeout(total=actual_timeout)
                    ) as res:
                        try:
                            data = await res.json()
                            if isinstance(data, dict):
                                response = data.get("response")
                                if response:
                                    logger.info("Successfully received response from Qwen API")
                                    return response
                            
                            # Fallback to string conversion
                            response_str = str(data)
                            logger.warning("Unexpected response format from Qwen API")
                            return response_str
                            
                        except ContentTypeError:
                            text = await res.text()
                            logger.error("Unexpected content type from Qwen API: %s", text[:200])
                            return text
                            
            except asyncio.TimeoutError as e:
                last_exception = e
                logger.warning(
                    "Request timeout (attempt %d/%d) after %d seconds", 
                    attempt + 1, retries, actual_timeout
                )
                if attempt < retries - 1:
                    delay = RETRY_DELAY * (RETRY_BACKOFF ** attempt)
                    logger.info("Retrying in %.2f seconds...", delay)
                    await asyncio.sleep(delay)
                else:
                    logger.error("All retry attempts failed due to timeout")
                    raise
                    
            except ClientError as e:
                last_exception = e
                logger.warning(
                    "Client error (attempt %d/%d): %s", 
                    attempt + 1, retries, str(e)
                )
                if attempt < retries - 1:
                    delay = RETRY_DELAY * (RETRY_BACKOFF ** attempt)
                    logger.info("Retrying in %.2f seconds...", delay)
                    await asyncio.sleep(delay)
                else:
                    logger.error("All retry attempts failed due to client error")
                    return None
                    
            except Exception as e:
                last_exception = e
                logger.exception("Unexpected error calling Qwen API (attempt %d/%d): %s", attempt + 1, retries, e)
                if attempt < retries - 1:
                    delay = RETRY_DELAY * (RETRY_BACKOFF ** attempt)
                    logger.info("Retrying in %.2f seconds...", delay)
                    await asyncio.sleep(delay)
                else:
                    logger.error("All retry attempts failed due to unexpected error")
                    return None
        
        # Should not reach here, but just in case
        if last_exception:
            logger.error("Request failed after all retries: %s", last_exception)
        return None


# Global singleton instance
agent = Agent()
