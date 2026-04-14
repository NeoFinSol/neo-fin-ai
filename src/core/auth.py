"""API Key authentication module."""

import hmac
import logging
from typing import Optional

from fastapi import Depends, HTTPException, Security, status
from fastapi.security import APIKeyHeader

from src.models.settings import app_settings

logger = logging.getLogger(__name__)

API_KEY_HEADER = APIKeyHeader(name="X-API-Key", auto_error=False)


def _api_keys_match(configured_key: str, provided_key: str) -> bool:
    """Compare API keys without transforming either operand."""
    return hmac.compare_digest(
        provided_key.encode("utf-8"),
        configured_key.encode("utf-8"),
    )


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

    if not _api_keys_match(app_settings.api_key, api_key_header):
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

    if _api_keys_match(app_settings.api_key, api_key_header):
        return api_key_header

    return None
