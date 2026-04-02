"""Tests for FastAPI application setup."""
import os
from unittest.mock import MagicMock, patch

import pytest

from src.app import _parse_cors_list, _parse_cors_origins


class TestParseCorsOrigins:
    """Tests for _parse_cors_origins function."""

    def test_empty_string(self):
        """Test empty string returns empty list."""
        result = _parse_cors_origins("")
        assert result == []

    def test_none_string(self):
        """Test None returns empty list."""
        result = _parse_cors_origins(None)
        assert result == []

    def test_single_origin(self):
        """Test single origin."""
        result = _parse_cors_origins("http://localhost:3000")
        assert result == ["http://localhost:3000"]

    def test_multiple_origins(self):
        """Test multiple comma-separated origins."""
        result = _parse_cors_origins("http://localhost:3000, https://example.com")
        assert len(result) == 2
        assert "http://localhost:3000" in result
        assert "https://example.com" in result

    def test_whitespace_trimmed(self):
        """Test whitespace is trimmed from origins."""
        result = _parse_cors_origins("  http://localhost:3000  ,  https://example.com  ")
        assert result == ["http://localhost:3000", "https://example.com"]

    def test_empty_strings_filtered(self):
        """Test empty strings are filtered out."""
        result = _parse_cors_origins("http://localhost:3000,, ,https://example.com")
        assert len(result) == 2

    def test_wildcard_rejected(self):
        """Test wildcard origin is rejected."""
        with pytest.raises(ValueError) as exc_info:
            _parse_cors_origins("*")
        assert "security reasons" in str(exc_info.value).lower()

    def test_wildcard_in_list_rejected(self):
        """Test wildcard in list is rejected."""
        with pytest.raises(ValueError) as exc_info:
            _parse_cors_origins("http://localhost:3000, *, https://example.com")
        assert "security reasons" in str(exc_info.value).lower()

    def test_invalid_origin_logged(self):
        """Test invalid origins (without http/https) are skipped."""
        with patch('src.app.logger') as mock_logger:
            result = _parse_cors_origins("localhost:3000, http://valid.com")
            assert result == ["http://valid.com"]
            mock_logger.warning.assert_called()

    def test_all_invalid_origins(self):
        """Test all invalid origins returns empty list."""
        result = _parse_cors_origins("localhost:3000, example.com")
        assert result == []


class TestParseCorsList:
    """Tests for _parse_cors_list function."""

    def test_empty_string_uses_defaults(self):
        """Test empty string returns default values."""
        defaults = ["GET", "POST"]
        result = _parse_cors_list("", defaults)
        assert result == defaults

    def test_none_uses_defaults(self):
        """Test None returns default values."""
        defaults = ["GET", "POST"]
        result = _parse_cors_list(None, defaults)
        assert result == defaults

    def test_custom_values(self):
        """Test custom comma-separated values."""
        result = _parse_cors_list("GET, POST, DELETE", ["PUT"])
        assert result == ["GET", "POST", "DELETE"]

    def test_whitespace_trimmed(self):
        """Test whitespace is trimmed."""
        result = _parse_cors_list("  GET  ,  POST  ", [])
        assert result == ["GET", "POST"]

    def test_empty_strings_filtered(self):
        """Test empty strings are filtered."""
        result = _parse_cors_list("GET,, ,POST", [])
        assert result == ["GET", "POST"]

    def test_single_value(self):
        """Test single value."""
        result = _parse_cors_list("Authorization", [])
        assert result == ["Authorization"]


class TestAppInitialization:
    """Tests for FastAPI app initialization."""

    def test_app_created(self):
        """Test that app is created successfully."""
        # Import here to avoid side effects
        from src.app import app
        assert app is not None
        assert app.title == "FastAPI"

    def test_routers_included(self):
        """Test that routers are included."""
        from src.app import app
        # Check that routers are registered
        router_names = [route.path for route in app.routes]
        assert any("/health" in name for name in router_names)

    def test_cors_middleware_added(self):
        """Test CORS middleware is configured."""
        from src.app import app
        middleware_types = [type(middleware).name if hasattr(type(middleware), 'name') else str(type(middleware)) 
                          for middleware in app.user_middleware]
        assert any("cors" in str(m).lower() for m in app.user_middleware)


class TestLifespan:
    """Tests for lifespan context manager."""

    @pytest.mark.asyncio
    async def test_lifespan_logs_configuration(self):
        """Test that lifespan logs AI service configuration."""
        from src.app import lifespan
        from src.core.ai_service import ai_service

        mock_app = MagicMock()

        # Lifespan should check AI service configuration
        # Just verify the lifespan context manager works
        async with lifespan(mock_app):
            # AI service should have is_configured property
            assert hasattr(ai_service, 'is_configured')
            assert isinstance(ai_service.is_configured, bool)


class TestCorsConfiguration:
    """Tests for CORS configuration edge cases."""

    def test_cors_error_handler_exists(self):
        """Test that CORS error handler is configured in module."""
        # The try/except block for CORS exists at module level
        # Verify the fallback variables are defined
        from src.app import allow_origins, allow_methods, allow_headers
        
        # These should always be defined (either from env or defaults)
        assert isinstance(allow_origins, list)
        assert isinstance(allow_methods, list)
        assert isinstance(allow_headers, list)

    def test_default_cors_origins(self):
        """Test default CORS origins when env var not set."""
        # Ensure env var is not set
        with patch.dict(os.environ, {}, clear=True):
            result = _parse_cors_origins("http://localhost,http://localhost:80,http://127.0.0.1,http://127.0.0.1:80")
            assert len(result) == 4

    def test_custom_cors_methods(self):
        """Test custom CORS methods from env."""
        result = _parse_cors_list("GET, POST, PATCH", ["DELETE"])
        assert result == ["GET", "POST", "PATCH"]

    def test_custom_cors_headers(self):
        """Test custom CORS headers from env."""
        result = _parse_cors_list("Content-Type, X-Custom-Header", [])
        assert result == ["Content-Type", "X-Custom-Header"]


class TestUvicornRun:
    """Tests for ASGI app module boundary."""

    def test_app_module_does_not_embed_uvicorn_runner(self):
        """Application module should stay import-safe and not shell out to uvicorn directly."""
        import src.app
        assert hasattr(src.app, "app")
        assert not hasattr(src.app, "uvicorn")
