"""
Security utility functions for NeoFin AI.

Low-level helpers for credential redaction and safe logging.
Lives in utils/ so that db/ and other layers can import without
creating upward dependencies into core/.
"""

import re


def get_safe_db_url_for_logging(db_url: str) -> str:
    """
    Return a safe version of a database URL for logging.

    Removes all credentials, keeping only the host and database name.

    Args:
        db_url: The database URL (may contain credentials).

    Returns:
        str: URL with credentials replaced by '***REDACTED***'.

    Examples:
        >>> get_safe_db_url_for_logging("postgresql://user:pass@localhost:5432/db")
        'postgresql://***REDACTED***@localhost:5432/db'
    """
    if not db_url:
        return "***"

    try:
        pattern = r"^(.+://)[^@]+(@.+)$"
        match = re.match(pattern, db_url)
        if match:
            return f"{match.group(1)}***REDACTED***{match.group(2)}"
        return "***REDACTED***"
    except Exception:
        return "***URL_PARSE_ERROR***"
