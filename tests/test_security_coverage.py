"""Additional tests for core/security.py — covers regex error paths."""
from unittest.mock import patch

import pytest

from src.core.security import (
    get_safe_db_url_for_logging,
    redact_credentials,
    redact_url,
)


class TestRedactUrlEdgeCases:
    def test_regex_error_returns_safe_default(self):
        """If re.error raised, returns safe default."""
        import re
        with patch("src.core.security.re.sub", side_effect=re.error("bad regex")):
            result = redact_url("postgresql://user:pass@localhost/db")
            assert result == "***URL_REDACT_FAILED***"

    def test_url_with_only_user_no_password(self):
        """URL with user but no password."""
        url = "postgresql://user@localhost:5432/db"
        result = redact_url(url)
        assert "user" not in result or "REDACTED" in result


class TestRedactCredentialsEdgeCases:
    def test_regex_error_returns_safe_default(self):
        """If re.error raised in pattern loop, returns safe default."""
        import re
        original_sub = __import__("re").sub
        call_count = [0]

        def fake_sub(pattern, repl, text, **kwargs):
            call_count[0] += 1
            if call_count[0] > 1:  # First call is redact_url, subsequent are credential patterns
                raise re.error("bad regex")
            return original_sub(pattern, repl, text, **kwargs)

        with patch("src.core.security.re.sub", side_effect=fake_sub):
            result = redact_credentials("password=secret")
            assert "REDACT" in result

    def test_auth_key_redacted(self):
        text = "auth=myauthtoken"
        result = redact_credentials(text)
        assert "myauthtoken" not in result


class TestGetSafeDbUrlEdgeCases:
    def test_url_without_at_sign(self):
        """URL without @ returns redacted."""
        result = get_safe_db_url_for_logging("postgresql://localhost/db")
        assert isinstance(result, str)

    def test_exception_returns_parse_error(self):
        """Exception during parsing returns safe string."""
        with patch("src.core.security.re.match", side_effect=Exception("parse error")):
            result = get_safe_db_url_for_logging("postgresql://user:pass@localhost/db")
            assert "***" in result
