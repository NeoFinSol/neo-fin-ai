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

# Development mode flag - explicitly disable authentication for local development
DEV_MODE: bool = os.getenv("DEV_MODE", "0") == "1"


async def get_api_key(
    api_key_header: str = Security(API_KEY_HEADER),
) -> str:
    """
    Validate API Key from request header.
    
    In production (DEV_MODE=0 or not set):
        - API_KEY must be set in environment
        - Valid API key must be provided in X-API-Key header
    
    In development (DEV_MODE=1):
        - Authentication is disabled
        - Any request is allowed (including without API key)
    
    Args:
        api_key_header: API Key from X-API-Key header
        
    Returns:
        str: Validated API key or 'dev-mode' in development
        
    Raises:
        HTTPException: If API key is missing or invalid (production only)
        RuntimeError: If API_KEY not set in production (fail-fast)
    """
    # Check if API_KEY is set - fail fast in production
    if not API_KEY and not DEV_MODE:
        logger.error(
            "API_KEY environment variable is not set and DEV_MODE is not enabled. "
            "Set API_KEY for production or DEV_MODE=1 for local development."
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Server configuration error: API_KEY not set",
        )
    
    # Development mode - allow requests without authentication
    if DEV_MODE:
        logger.debug("Development mode: authentication disabled")
        return "dev-mode"
    
    # Production mode - require valid API key
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
    if DEV_MODE:
        return None
    
    if not API_KEY:
        return None
    
    if not api_key_header:
        return None
    
    if api_key_header == API_KEY:
        return api_key_header
    
    return None
