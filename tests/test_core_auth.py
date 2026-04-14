"""Tests for core/auth.py — API key authentication."""

from unittest.mock import patch

import pytest
from fastapi import HTTPException

from src.core.auth import get_api_key, optional_auth


class TestGetApiKey:
    """Tests for get_api_key dependency."""

    @pytest.mark.asyncio
    async def test_dev_mode_bypasses_auth(self):
        """In dev mode, auth is skipped and None is returned."""
        with patch("src.core.auth.app_settings") as mock_settings:
            mock_settings.dev_mode = True
            result = await get_api_key(api_key_header="any-key")
            assert result is None

    @pytest.mark.asyncio
    async def test_no_api_key_configured_raises_500(self):
        """If API_KEY not set and not dev mode, raise 500."""
        with patch("src.core.auth.app_settings") as mock_settings:
            mock_settings.dev_mode = False
            mock_settings.api_key = None
            with pytest.raises(HTTPException) as exc_info:
                await get_api_key(api_key_header=None)
            assert exc_info.value.status_code == 500
            assert "API_KEY not set" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_missing_header_raises_401(self):
        """Missing X-API-Key header raises 401."""
        with patch("src.core.auth.app_settings") as mock_settings:
            mock_settings.dev_mode = False
            mock_settings.api_key = "secret"
            with pytest.raises(HTTPException) as exc_info:
                await get_api_key(api_key_header=None)
            assert exc_info.value.status_code == 401
            assert "Missing API key" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_wrong_key_raises_401(self):
        """Wrong API key raises 401."""
        with patch("src.core.auth.app_settings") as mock_settings:
            mock_settings.dev_mode = False
            mock_settings.api_key = "correct-key"
            with pytest.raises(HTTPException) as exc_info:
                await get_api_key(api_key_header="wrong-key")
            assert exc_info.value.status_code == 401
            assert "Invalid API key" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_correct_key_returns_key(self):
        """Correct API key is returned."""
        with patch("src.core.auth.app_settings") as mock_settings:
            mock_settings.dev_mode = False
            mock_settings.api_key = "my-secret"
            result = await get_api_key(api_key_header="my-secret")
            assert result == "my-secret"

    @pytest.mark.asyncio
    async def test_uses_compare_digest_for_equality_check(self):
        """Equality check must use hmac.compare_digest."""
        with patch("src.core.auth.app_settings") as mock_settings, patch(
            "src.core.auth.hmac.compare_digest",
            return_value=True,
        ) as mock_compare:
            mock_settings.dev_mode = False
            mock_settings.api_key = "secret"

            result = await get_api_key(api_key_header="secret")

        assert result == "secret"
        mock_compare.assert_called_once_with("secret", "secret")

    @pytest.mark.asyncio
    async def test_exact_match_semantics_reject_trailing_whitespace(self):
        """Comparison must not trim inputs before comparing."""
        with patch("src.core.auth.app_settings") as mock_settings:
            mock_settings.dev_mode = False
            mock_settings.api_key = "secret"

            with pytest.raises(HTTPException) as exc_info:
                await get_api_key(api_key_header="secret ")

        assert exc_info.value.status_code == 401
        assert "Invalid API key" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_exact_match_semantics_reject_case_changes(self):
        """Comparison must remain case-sensitive."""
        with patch("src.core.auth.app_settings") as mock_settings:
            mock_settings.dev_mode = False
            mock_settings.api_key = "secret"

            with pytest.raises(HTTPException) as exc_info:
                await get_api_key(api_key_header="Secret")

        assert exc_info.value.status_code == 401
        assert "Invalid API key" in exc_info.value.detail


class TestOptionalAuth:
    """Tests for optional_auth dependency."""

    @pytest.mark.asyncio
    async def test_dev_mode_returns_none(self):
        with patch("src.core.auth.app_settings") as mock_settings:
            mock_settings.dev_mode = True
            result = await optional_auth(api_key_header="any")
            assert result is None

    @pytest.mark.asyncio
    async def test_no_api_key_configured_returns_none(self):
        with patch("src.core.auth.app_settings") as mock_settings:
            mock_settings.dev_mode = False
            mock_settings.api_key = None
            result = await optional_auth(api_key_header="any")
            assert result is None

    @pytest.mark.asyncio
    async def test_missing_header_returns_none(self):
        with patch("src.core.auth.app_settings") as mock_settings:
            mock_settings.dev_mode = False
            mock_settings.api_key = "secret"
            result = await optional_auth(api_key_header=None)
            assert result is None

    @pytest.mark.asyncio
    async def test_wrong_key_returns_none(self):
        with patch("src.core.auth.app_settings") as mock_settings:
            mock_settings.dev_mode = False
            mock_settings.api_key = "correct"
            result = await optional_auth(api_key_header="wrong")
            assert result is None

    @pytest.mark.asyncio
    async def test_correct_key_returns_key(self):
        with patch("src.core.auth.app_settings") as mock_settings:
            mock_settings.dev_mode = False
            mock_settings.api_key = "correct"
            result = await optional_auth(api_key_header="correct")
            assert result == "correct"
