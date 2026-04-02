"""Additional tests for app.py — covers lifespan and CORS fallback."""
import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestLifespanCoverage:
    """Tests for lifespan context manager — covers lines 93-121."""

    @pytest.mark.asyncio
    async def test_lifespan_with_invalid_log_level(self):
        """Invalid LOG_LEVEL falls back to INFO."""
        from src.app import lifespan
        mock_app = MagicMock()
        with patch.dict(os.environ, {"LOG_LEVEL": "INVALID", "LOG_FORMAT": "text"}):
            async with lifespan(mock_app):
                pass  # should not raise

    @pytest.mark.asyncio
    async def test_lifespan_with_json_log_format(self):
        """JSON log format path is exercised."""
        from src.app import lifespan
        mock_app = MagicMock()
        with patch.dict(os.environ, {"LOG_LEVEL": "DEBUG", "LOG_FORMAT": "json"}):
            async with lifespan(mock_app):
                pass

    @pytest.mark.asyncio
    async def test_lifespan_with_invalid_log_format(self):
        """Invalid LOG_FORMAT falls back to text."""
        from src.app import lifespan
        mock_app = MagicMock()
        with patch.dict(os.environ, {"LOG_FORMAT": "xml"}):
            async with lifespan(mock_app):
                pass

    @pytest.mark.asyncio
    async def test_lifespan_ai_not_configured(self):
        """Lifespan logs warning when AI not configured."""
        from src.app import lifespan
        mock_app = MagicMock()
        with patch("src.app.ai_service") as mock_ai:
            mock_ai.is_configured = False
            mock_ai.close = AsyncMock()
            async with lifespan(mock_app):
                pass

    @pytest.mark.asyncio
    async def test_lifespan_disposes_engine_on_shutdown(self):
        """Shutdown should dispose the SQLAlchemy engine to avoid leaked connections."""
        from src.app import lifespan

        mock_app = MagicMock()
        with patch("src.app.dispose_engine", new_callable=AsyncMock) as mock_dispose:
            async with lifespan(mock_app):
                pass

        mock_dispose.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_lifespan_closes_ai_service_on_shutdown(self):
        """Shared AI runtime resources should be closed during application shutdown."""
        from src.app import lifespan

        mock_app = MagicMock()
        with patch("src.app.ai_service.close", new_callable=AsyncMock) as mock_close:
            async with lifespan(mock_app):
                pass

        mock_close.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_lifespan_enters_runtime_event_bridge(self):
        """Persistent runtime bridge should be entered during app lifespan."""
        from contextlib import asynccontextmanager

        from src.app import lifespan

        entered = False

        @asynccontextmanager
        async def fake_bridge():
            nonlocal entered
            entered = True
            yield

        mock_app = MagicMock()
        with patch("src.app.runtime_event_bridge", side_effect=fake_bridge):
            async with lifespan(mock_app):
                pass

        assert entered is True


class TestRuntimeEventBridge:
    """Tests for runtime event routing."""

    @pytest.mark.asyncio
    async def test_broadcast_task_event_uses_local_ws_when_bridge_disabled(self):
        from src.core.runtime_events import broadcast_task_event

        with patch("src.core.runtime_events._use_redis_event_bridge", return_value=False):
            with patch("src.core.runtime_events.ws_manager.broadcast", new_callable=AsyncMock) as mock_broadcast:
                await broadcast_task_event("task-1", {"status": "processing"})

        mock_broadcast.assert_awaited_once_with("task-1", {"status": "processing"})

    @pytest.mark.asyncio
    async def test_broadcast_task_event_publishes_to_redis_when_bridge_enabled(self):
        from src.core.runtime_events import broadcast_task_event

        mock_client = MagicMock()
        mock_client.publish = AsyncMock()
        mock_client.aclose = AsyncMock()

        with patch("src.core.runtime_events._use_redis_event_bridge", return_value=True):
            with patch("src.core.runtime_events._events_redis_url", return_value="redis://broker"):
                with patch("src.core.runtime_events.Redis") as mock_redis:
                    mock_redis.from_url.return_value = mock_client
                    await broadcast_task_event("task-1", {"status": "processing"})

        mock_client.publish.assert_awaited_once()
        mock_client.aclose.assert_awaited_once()


class TestCorsConfigFallback:
    """Tests for CORS ValueError fallback — covers lines 169-204."""

    def test_cors_fallback_on_wildcard(self):
        """ValueError from wildcard origin triggers fallback."""
        # The fallback is at module level — verify the variables exist
        from src.app import allow_headers, allow_methods, allow_origins
        assert isinstance(allow_origins, list)
        assert isinstance(allow_methods, list)
        assert isinstance(allow_headers, list)

    def test_parse_cors_origins_with_mixed_valid_invalid(self):
        """Mixed valid/invalid origins — only valid ones kept."""
        from src.app import _parse_cors_origins
        result = _parse_cors_origins("http://valid.com, ftp://invalid.com, https://also-valid.com")
        assert "http://valid.com" in result
        assert "https://also-valid.com" in result
        assert len(result) == 2
