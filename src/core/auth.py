"""API Key authentication module."""

import logging
from typing import Optional

from fastapi import Depends, HTTPException, Security, status
from fastapi.security import APIKeyHeader

from src.models.settings import app_settings

logger = logging.getLogger(__name__)

API_KEY_HEADER = APIKeyHeader(name="X-API-Key", auto_error=False)


async def get_api_key(
    api_key_header: str = Security(API_KEY_HEADER),
) -> Optional[str]:
    """Validate API Key from request header."""
    if app_settings.dev_mode:
        logger.debug("Development mode: authentication disabled")
        return None

    if not app_settings.api_key:
        logger.error(
            "API_KEY environment variable is not set and DEV_MODE is not enabled."
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Server configuration error: API_KEY not set",
        )

    if not api_key_header:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing API key. Provide it via X-API-Key header.",
            headers={"WWW-Authenticate": "ApiKey"},
        )

    if api_key_header != app_settings.api_key:
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
    """Optional authentication."""
    if app_settings.dev_mode:
        return None

    if not app_settings.api_key:
        return None

    if not api_key_header:
        return None

    if api_key_header == app_settings.api_key:
        return api_key_header

    return None
