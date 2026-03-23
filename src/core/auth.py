"""API Key authentication module."""
import logging
import os
from typing import Optional

from fastapi import Depends, HTTPException, Security, status
from fastapi.security import APIKeyHeader

logger = logging.getLogger(__name__)

# API Key header name
API_KEY_HEADER = APIKeyHeader(name="X-API-Key", auto_error=False)

# API Key from environment variable
API_KEY: Optional[str] = os.getenv("API_KEY")


async def get_api_key(
    api_key_header: str = Security(API_KEY_HEADER),
) -> str:
    """
    Validate API Key from request header.
    
    Args:
        api_key_header: API Key from X-API-Key header
        
    Returns:
        str: Validated API key
        
    Raises:
        HTTPException: If API key is missing or invalid
    """
    if not API_KEY:
        # If API_KEY is not set, authentication is disabled (development mode)
        # This allows local development without authentication
        logger.warning("API_KEY not set - authentication disabled (development mode)")
        return "dev-mode-no-key"
    
    if not api_key_header:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing API key. Provide it via X-API-Key header.",
            headers={"WWW-Authenticate": "ApiKey"},
        )
    
    if api_key_header != API_KEY:
        logger.warning("Invalid API key attempt")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
            headers={"WWW-Authenticate": "ApiKey"},
        )
    
    return api_key_header


async def optional_auth(
    api_key_header: str = Security(API_KEY_HEADER),
) -> Optional[str]:
    """
    Optional authentication - returns API key if provided and valid, None otherwise.
    Use this for endpoints that work with or without authentication.
    
    Args:
        api_key_header: API Key from X-API-Key header
        
    Returns:
        Optional[str]: API key if valid, None otherwise
    """
    if not API_KEY:
        return None
    
    if not api_key_header:
        return None
    
    if api_key_header == API_KEY:
        return api_key_header
    
    return None
