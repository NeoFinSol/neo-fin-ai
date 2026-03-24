"""Tests for core/security.py — credential redaction utilities."""
import pytest

from src.core.security import redact_url, redact_credentials, get_safe_db_url_for_logging


class TestRedactUrl:
    """Tests for redact_url function."""

    def test_redacts_user_and_password(self):
        url = "postgresql://user:password@localhost:5432/db"
        result = redact_url(url)
        assert "user" not in result
        assert "password" not in result
        assert "localhost" in result
        assert "***REDACTED***" in result

    def test_redacts_asyncpg_url(self):
        url = "postgresql+asyncpg://admin:secret@db.host:5432/neofin"
        result = redact_url(url)
        assert "admin" not in result
        assert "secret" not in result
        assert "db.host" in result

    def test_url_without_credentials_unchanged(self):
        url = "postgresql://localhost:5432/db"
        result = redact_url(url)
        # No credentials to redact — should not crash
        assert "localhost" in result

    def test_empty_string_returns_empty(self):
        assert redact_url("") == ""

    def test_none_returns_none(self):
        assert redact_url(None) is None

    def test_not_a_url_returned_as_is(self):
        result = redact_url("not-a-url")
        assert result == "not-a-url"

    def test_http_url_redacted(self):
        url = "http://user:pass@example.com/api"
        result = redact_url(url)
        assert "user" not in result
        assert "pass" not in result

    def test_custom_replacement(self):
        url = "postgresql://user:pass@localhost/db"
        result = redact_url(url, replacement="[HIDDEN]")
        assert "[HIDDEN]" in result


class TestRedactCredentials:
    """Tests for redact_credentials function."""

    def test_redacts_password_key(self):
        text = "connection: password=mysecret123"
        result = redact_credentials(text)
        assert "mysecret123" not in result
        assert "***REDACTED***" in result

    def test_redacts_secret_key(self):
        text = "config: secret=abc123xyz"
        result = redact_credentials(text)
        assert "abc123xyz" not in result

    def test_redacts_api_key(self):
        text = "api_key=sk-1234567890abcdef"
        result = redact_credentials(text)
        assert "sk-1234567890abcdef" not in result

    def test_redacts_token(self):
        text = "token=mytoken123"
        result = redact_credentials(text)
        assert "mytoken123" not in result

    def test_empty_string_returns_empty(self):
        assert redact_credentials("") == ""

    def test_none_returns_none(self):
        assert redact_credentials(None) is None

    def test_plain_text_unchanged(self):
        text = "Hello, world! No credentials here."
        result = redact_credentials(text)
        assert result == text

    def test_url_in_text_redacted(self):
        text = "Connecting to postgresql://user:pass@localhost/db"
        result = redact_credentials(text)
        assert "pass" not in result


class TestGetSafeDbUrlForLogging:
    """Tests for get_safe_db_url_for_logging function."""

    def test_redacts_credentials(self):
        url = "postgresql+asyncpg://admin:secret@localhost:5432/neofin"
        result = get_safe_db_url_for_logging(url)
        assert "admin" not in result
        assert "secret" not in result

    def test_empty_returns_stars(self):
        result = get_safe_db_url_for_logging("")
        assert result == "***"

    def test_none_returns_stars(self):
        result = get_safe_db_url_for_logging(None)
        assert result == "***"

    def test_url_without_credentials(self):
        url = "postgresql://localhost:5432/db"
        result = get_safe_db_url_for_logging(url)
        # Should not crash, return something safe
        assert isinstance(result, str)
        assert len(result) > 0
