"""Tests for routers/system.py — health check endpoints."""

from datetime import datetime, timedelta
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from src.app import app


def _assert_utc_timestamp(value: str) -> None:
    parsed = datetime.fromisoformat(value)
    assert parsed.tzinfo is not None
    assert parsed.utcoffset() == timedelta(0)


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
        _assert_utc_timestamp(data["timestamp"])


class TestHealthzCheck:
    """Tests for GET /system/healthz."""

    def test_healthz_db_healthy_ai_configured(self):
        with patch(
            "src.routers.system.check_database_connectivity",
            new_callable=AsyncMock,
            return_value=True,
        ), patch("src.routers.system.ai_service") as mock_ai:
            mock_ai.is_configured = True
            mock_ai.is_available = True
            with TestClient(app) as client:
                response = client.get("/system/healthz")
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "healthy"
            assert data["components"]["database"] == "healthy"
            assert data["components"]["ai_service"] == "healthy"

    def test_healthz_db_unhealthy(self):
        with patch(
            "src.routers.system.check_database_connectivity",
            new_callable=AsyncMock,
            return_value=False,
        ), patch("src.routers.system.ai_service") as mock_ai:
            mock_ai.is_configured = False
            with TestClient(app) as client:
                response = client.get("/system/healthz")
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "degraded"
            assert data["components"]["database"] == "unhealthy"

    def test_healthz_ai_not_configured(self):
        with patch(
            "src.routers.system.check_database_connectivity",
            new_callable=AsyncMock,
            return_value=True,
        ), patch("src.routers.system.ai_service") as mock_ai:
            mock_ai.is_configured = False
            with TestClient(app) as client:
                response = client.get("/system/healthz")
            assert response.status_code == 200
            data = response.json()
            assert data["components"]["ai_service"] == "not_configured"

    def test_healthz_has_timestamp(self):
        with patch(
            "src.routers.system.check_database_connectivity",
            new_callable=AsyncMock,
            return_value=True,
        ), patch("src.routers.system.ai_service") as mock_ai:
            mock_ai.is_configured = True
            mock_ai.is_available = True
            with TestClient(app) as client:
                response = client.get("/system/healthz")
            data = response.json()
            assert "timestamp" in data
            _assert_utc_timestamp(data["timestamp"])


class TestReadinessCheck:
    """Tests for GET /system/ready."""

    def test_ready_when_db_available(self):
        with patch(
            "src.routers.system.check_database_connectivity",
            new_callable=AsyncMock,
            return_value=True,
        ):
            with TestClient(app) as client:
                response = client.get("/system/ready")
            assert response.status_code == 200
            assert response.json() == {"status": "ready"}

    def test_not_ready_when_db_unavailable(self):
        with patch(
            "src.routers.system.check_database_connectivity",
            new_callable=AsyncMock,
            return_value=False,
        ):
            with TestClient(app) as client:
                response = client.get("/system/ready")
            assert response.status_code == 503
            assert (
                response.json()["detail"]
                == "Service not ready: database connection failed"
            )
