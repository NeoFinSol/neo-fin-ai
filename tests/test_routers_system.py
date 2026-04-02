"""Tests for routers/system.py — health check endpoints."""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from src.app import app


class TestHealthCheck:
    """Tests for GET /system/health."""

    def test_health_returns_ok(self):
        with TestClient(app) as client:
            response = client.get("/system/health")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert data["status"] == "ok"
        assert "services" in data
        assert "timestamp" in data


class TestHealthzCheck:
    """Tests for GET /system/healthz."""

    def test_healthz_db_healthy_ai_configured(self):
        mock_engine = MagicMock()
        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock()
        mock_conn.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_conn.__aexit__ = AsyncMock(return_value=False)
        mock_engine.connect = MagicMock(return_value=mock_conn)

        with patch("src.routers.system.get_engine", return_value=mock_engine), \
             patch("src.routers.system.ai_service") as mock_ai:
            mock_ai.is_configured = True
            with TestClient(app) as client:
                response = client.get("/system/healthz")
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "healthy"
            assert data["components"]["database"] == "healthy"
            assert data["components"]["ai_service"] == "healthy"

    def test_healthz_db_unhealthy(self):
        with patch("src.routers.system.get_engine", side_effect=Exception("DB down")), \
             patch("src.routers.system.ai_service") as mock_ai:
            mock_ai.is_configured = False
            with TestClient(app) as client:
                response = client.get("/system/healthz")
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "degraded"
            assert data["components"]["database"] == "unhealthy"

    def test_healthz_ai_not_configured(self):
        mock_engine = MagicMock()
        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock()
        mock_conn.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_conn.__aexit__ = AsyncMock(return_value=False)
        mock_engine.connect = MagicMock(return_value=mock_conn)

        with patch("src.routers.system.get_engine", return_value=mock_engine), \
             patch("src.routers.system.ai_service") as mock_ai:
            mock_ai.is_configured = False
            with TestClient(app) as client:
                response = client.get("/system/healthz")
            assert response.status_code == 200
            data = response.json()
            assert data["components"]["ai_service"] == "not_configured"

    def test_healthz_has_timestamp(self):
        mock_engine = MagicMock()
        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock()
        mock_conn.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_conn.__aexit__ = AsyncMock(return_value=False)
        mock_engine.connect = MagicMock(return_value=mock_conn)

        with patch("src.routers.system.get_engine", return_value=mock_engine), \
             patch("src.routers.system.ai_service") as mock_ai:
            mock_ai.is_configured = True
            with TestClient(app) as client:
                response = client.get("/system/healthz")
            assert "timestamp" in response.json()


class TestReadinessCheck:
    """Tests for GET /system/ready."""

    def test_ready_when_db_available(self):
        mock_engine = MagicMock()
        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock()
        mock_conn.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_conn.__aexit__ = AsyncMock(return_value=False)
        mock_engine.connect = MagicMock(return_value=mock_conn)

        with patch("src.routers.system.get_engine", return_value=mock_engine):
            with TestClient(app) as client:
                response = client.get("/system/ready")
            assert response.status_code == 200
            assert response.json() == {"status": "ready"}

    def test_not_ready_when_db_unavailable(self):
        with patch("src.routers.system.get_engine", side_effect=Exception("DB unavailable")):
            with TestClient(app) as client:
                response = client.get("/system/ready")
            assert response.status_code == 503
            assert "not ready" in response.json()["detail"]
