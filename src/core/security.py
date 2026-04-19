"""
Security utilities for NeoFin AI.

This module provides functions for handling sensitive data securely,
including credential redaction and secure random generation.
"""

import re

# Re-export from utils so existing imports from core.security keep working
from src.utils.security_utils import get_safe_db_url_for_logging

__all__ = ["get_safe_db_url_for_logging", "redact_url", "redact_credentials"]


def redact_url(url: str, replacement: str = "***REDACTED***") -> str:
    """
    Redact credentials from a URL string.

    Handles various URL formats:
    - postgresql://user:pass@host:port/db
    - postgresql+asyncpg://user:pass@host:port/db
    - http://user:pass@host/path

    Args:
        url: The URL string to redact
        replacement: The replacement string for credentials

    Returns:
        str: URL with credentials redacted, or original if not a URL

    Examples:
        >>> redact_url("postgresql://user:pass@localhost/db")
        'postgresql://***REDACTED***@localhost/db'

        >>> redact_url("not-a-url")
        'not-a-url'
    """
    if not url:
        return url

    # Pattern to match credentials in URLs
    # Matches: scheme://user:pass@host or scheme://user@host
    pattern = r"://([^:@/]+(?::[^@/]+)?@)"

    try:
        redacted = re.sub(pattern, f"://{replacement}@", url)
        return redacted
    except re.error:
        # If regex fails, return a safe default
        return "***URL_REDACT_FAILED***"


def redact_credentials(text: str, replacement: str = "***REDACTED***") -> str:
    """
    Redact potential credentials from any text string.

    This is a more general function that attempts to find and redact
    credential-like patterns in any text, not just URLs.

    Args:
        text: The text to redact
        replacement: The replacement string

    Returns:
        str: Text with credentials redacted
    """
    if not text:
        return text

    # First, redact URLs
    text = redact_url(text, replacement)

    # Redact patterns that look like passwords/secrets
    # Matches: password=xxx, secret=xxx, api_key=xxx, token=xxx
    patterns = [
        (r"(password\s*[=:]\s*)[^\s,;]+", r"\1" + replacement),
        (r"(secret\s*[=:]\s*)[^\s,;]+", r"\1" + replacement),
        (r"(api_key\s*[=:]\s*)[^\s,;]+", r"\1" + replacement),
        (r"(token\s*[=:]\s*)[^\s,;]+", r"\1" + replacement),
        (r"(auth\s*[=:]\s*)[^\s,;]+", r"\1" + replacement),
    ]

    try:
        for pattern, repl in patterns:
            text = re.sub(pattern, repl, text, flags=re.IGNORECASE)
        return text
    except re.error:
        return "***REDACT_FAILED***"
