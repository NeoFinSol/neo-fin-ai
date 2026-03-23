import asyncio
import base64
import logging
import os
import ssl
from typing import Optional

import aiohttp
from aiohttp import ClientError, ClientTimeout, ContentTypeError

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 120  # seconds
MAX_RETRIES = 3
RETRY_DELAY = 1.0  # seconds
RETRY_BACKOFF = 2.0  # multiplier

# GigaChat API endpoints
GIGACHAT_AUTH_URL = "https://ngw.devices.sberbank.ru:9443/api/v2/oauth"
GIGACHAT_CHAT_URL = "https://gigachat.devices.sberbank.ru/api/v1/chat/completions"

# SSL context for GigaChat
# By default, use secure SSL verification.
# For development with self-signed certificates, set GIGACHAT_SSL_VERIFY=false
# WARNING: Disabling SSL verification exposes you to MITM attacks!
_gigachat_ssl_verify = os.getenv("GIGACHAT_SSL_VERIFY", "true").lower() != "false"

if _gigachat_ssl_verify:
    # Secure SSL verification (production mode)
    _gigachat_ssl_context = ssl.create_default_context()
    logger.info("GigaChat SSL verification enabled (secure)")
else:
    # Insecure SSL (development mode only!)
    _gigachat_ssl_context = ssl.create_default_context()
    _gigachat_ssl_context.check_hostname = False
    _gigachat_ssl_context.verify_mode = ssl.CERT_NONE
    logger.warning(
        "GigaChat SSL verification DISABLED! This is insecure and should only be used "
        "in development environments with self-signed certificates."
    )


class GigaChatAgent:
    """Agent for interacting with GigaChat AI API."""
    
    def __init__(self, timeout: int = DEFAULT_TIMEOUT):
        self._client_id: Optional[str] = None
        self._client_secret: Optional[str] = None
        self._auth_token: Optional[str] = None
        self._token_expires_at: float = 0
        self.model: str = "GigaChat-Pro"
        self.timeout = timeout
        self._configured: bool = False

    def set_config(
        self, 
        client_id: Optional[str], 
        client_secret: Optional[str],
        auth_url: str = GIGACHAT_AUTH_URL,
        chat_url: str = GIGACHAT_CHAT_URL,
    ) -> None:
        """
        Configure agent with GigaChat API credentials.
        
        Args:
            client_id: GigaChat Client ID
            client_secret: GigaChat Client Secret
            auth_url: OAuth authentication URL
            chat_url: Chat completions API URL
            
        Raises:
            ValueError: If client_id or client_secret is missing/empty
        """
        if not client_id or not client_id.strip():
            raise ValueError("GigaChat Client ID is required")
        
        if not client_secret or not client_secret.strip():
            raise ValueError("GigaChat Client Secret is required")
        
        self._client_id = client_id.strip()
        self._client_secret = client_secret.strip()
        self._auth_url = auth_url.rstrip('/')
        self._chat_url = chat_url.rstrip('/')
        self._configured = True
        logger.info("GigaChat agent configured")

    def _ensure_configured(self) -> None:
        """Ensure agent is configured before making requests."""
        if not self._configured or not self._client_id or not self._client_secret:
            raise ValueError(
                "GigaChat agent not configured. Call set_config(client_id, client_secret) first"
            )

    async def _get_access_token(self) -> str:
        """
        Get OAuth access token from GigaChat API.
        
        Returns:
            str: Access token for API calls
            
        Raises:
            ValueError: If authentication fails
        """
        import time
        
        # Check if we have a valid cached token
        if self._auth_token and time.time() < self._token_expires_at:
            logger.debug("Using cached GigaChat access token")
            return self._auth_token
        
        # Create Basic Auth header (base64 encoded client_id:client_secret)
        credentials = f"{self._client_id}:{self._client_secret}"
        encoded_credentials = base64.b64encode(credentials.encode('utf-8')).decode('utf-8')
        
        headers = {
            "Authorization": f"Basic {encoded_credentials}",
            "Content-Type": "application/x-www-form-urlencoded",
            "RqUID": "00000000-0000-0000-0000-000000000000",  # Required by GigaChat
        }
        
        data = {
            "scope": "GIGACHAT_API_PERS"
        }
        
        try:
            # Use TCPConnector with custom SSL context for GigaChat
            connector = aiohttp.TCPConnector(ssl=_gigachat_ssl_context)
            async with aiohttp.ClientSession(connector=connector) as session:
                async with session.post(
                    self._auth_url,
                    headers=headers,
                    data=data,
                    timeout=ClientTimeout(total=30)
                ) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        logger.error("GigaChat auth failed: %d - %s", response.status, error_text)
                        raise ValueError(f"GigaChat authentication failed: {response.status}")
                    
                    result = await response.json()
                    access_token = result.get("access_token")
                    expires_in = result.get("expires_in", 3600)  # Default 1 hour
                    
                    if not access_token:
                        raise ValueError("No access_token in GigaChat auth response")
                    
                    # Cache token (subtract 5 minutes to be safe)
                    self._auth_token = access_token
                    self._token_expires_at = time.time() + expires_in - 300
                    
                    logger.info("Successfully obtained GigaChat access token")
                    return access_token
                    
        except aiohttp.ClientError as e:
            logger.error("Failed to connect to GigaChat auth: %s", e)
            raise ValueError(f"GigaChat auth connection error: {e}")
        except Exception as e:
            logger.exception("Unexpected error during GigaChat authentication")
            raise ValueError(f"GigaChat auth error: {e}")

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
            ValueError: If agent is not configured
        """
        self._ensure_configured()
        
        actual_timeout = timeout or self.timeout
        try:
            async with asyncio.timeout(actual_timeout):
                return await self.request(
                    messages=input.get("tool_input", ""),
                    system=input.get("system"),
                )
        except asyncio.TimeoutError:
            logger.error("GigaChat request timeout after %d seconds", actual_timeout)
            raise

    async def request(
        self, 
        messages: str,
        system: Optional[str] = None,
        timeout: Optional[int] = None,
        retries: int = MAX_RETRIES,
    ) -> Optional[str]:
        """
        Send request to GigaChat API with retry logic.
        
        Args:
            messages: Message(s) to send (string or list of message dicts)
            system: Optional system prompt
            timeout: Request timeout in seconds
            retries: Number of retry attempts
            
        Returns:
            Optional[str]: API response or None
            
        Raises:
            ValueError: If agent is not configured
        """
        self._ensure_configured()

        actual_timeout = timeout or self.timeout
        last_exception: Optional[Exception] = None
        
        for attempt in range(retries):
            try:
                # Get access token
                access_token = await self._get_access_token()
                
                # Prepare request
                headers = {
                    "Authorization": f"Bearer {access_token}",
                    "Content-Type": "application/json",
                }
                
                # Format messages for GigaChat API
                if isinstance(messages, str):
                    messages_list = [{"role": "user", "content": messages}]
                else:
                    messages_list = messages
                
                # Add system message if provided
                if system:
                    messages_list.insert(0, {"role": "system", "content": system})
                
                req_json = {
                    "model": self.model,
                    "messages": messages_list,
                }
                
                # Use TCPConnector with custom SSL context for GigaChat
                connector = aiohttp.TCPConnector(ssl=_gigachat_ssl_context)
                async with aiohttp.ClientSession(connector=connector) as session:
                    async with session.post(
                        self._chat_url,
                        json=req_json,
                        headers=headers,
                        timeout=ClientTimeout(total=actual_timeout)
                    ) as res:
                        if res.status != 200:
                            error_text = await res.text()
                            logger.error("GigaChat API error %d: %s", res.status, error_text[:200])
                            
                            # Token might be expired, clear it
                            if res.status == 401:
                                self._auth_token = None
                                self._token_expires_at = 0
                            
                            if attempt < retries - 1:
                                continue  # Retry
                            return None
                        
                        try:
                            data = await res.json()
                            
                            # GigaChat response format:
                            # {
                            #   "choices": [
                            #     {
                            #       "message": {
                            #         "role": "assistant",
                            #         "content": "..."
                            #       }
                            #     }
                            #   ]
                            # }
                            choices = data.get("choices", [])
                            if choices and len(choices) > 0:
                                message = choices[0].get("message", {})
                                response = message.get("content", "")
                                
                                if response:
                                    logger.info("Successfully received response from GigaChat")
                                    return response
                            
                            logger.warning("Empty response from GigaChat API")
                            return None
                            
                        except ContentTypeError:
                            text = await res.text()
                            logger.error("Unexpected content type from GigaChat API: %s", text[:200])
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
                logger.exception("Unexpected error calling GigaChat API (attempt %d/%d): %s", attempt + 1, retries, e)
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
gigachat_agent = GigaChatAgent()
