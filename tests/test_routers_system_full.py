"""
Tests for routers/system.py health check endpoints.

Covers:
- GET /system/health (comprehensive health)
- GET /system/healthz (extended health)
- GET /system/ready (readiness check)
- GET /system/metrics (application metrics)
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from src.app import app


@pytest.fixture(scope="function")
def client(monkeypatch):
    """Create test client with mocked auth."""
    with patch("src.core.auth.app_settings") as mock_settings:
        mock_settings.dev_mode = True
        mock_settings.api_key = None
        
        with TestClient(app) as test_client:
            yield test_client


class TestHealthCheck:
    """Tests for GET /system/health endpoint."""

    def test_health_all_services_ok(self, client):
        """Test health check when all services are healthy."""
        mock_engine = MagicMock()
        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock()
        mock_conn.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_conn.__aexit__ = AsyncMock(return_value=False)
        mock_engine.connect = MagicMock(return_value=mock_conn)
        
        with patch("src.routers.system.get_engine", return_value=mock_engine), \
             patch("src.routers.system.ai_service") as mock_ai:
            mock_ai.is_configured = True
            mock_ai.is_available = True
            
            response = client.get("/system/health")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["services"]["db"] == "ok"
        assert data["services"]["ai"] == "ok"
        assert data["services"]["ocr"] == "ok"
        assert "timestamp" in data

    def test_health_db_down(self, client):
        """Test health check when database is down."""
        with patch("src.routers.system.get_engine", side_effect=Exception("DB down")), \
             patch("src.routers.system.ai_service") as mock_ai:
            mock_ai.is_configured = True
            mock_ai.is_available = True
            
            response = client.get("/system/health")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "down"
        assert data["services"]["db"] == "down"

    def test_health_ai_circuit_breaker_open(self, client):
        """Test health check when AI circuit breaker is open."""
        mock_engine = MagicMock()
        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock()
        mock_conn.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_conn.__aexit__ = AsyncMock(return_value=False)
        mock_engine.connect = MagicMock(return_value=mock_conn)
        
        with patch("src.routers.system.get_engine", return_value=mock_engine), \
             patch("src.routers.system.ai_service") as mock_ai:
            mock_ai.is_configured = True
            mock_ai.is_available = False
            mock_ai.get_circuit_breaker_status.return_value = {
                "state": "open",
                "failure_count": 5,
                "threshold": 5,
                "time_until_retry": 90
            }
            
            response = client.get("/system/health")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "degraded"
        assert data["services"]["ai"] == "degraded"
        assert "ai_circuit_breaker" in data

    def test_health_ai_not_configured(self, client):
        """Test health check when AI is not configured."""
        mock_engine = MagicMock()
        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock()
        mock_conn.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_conn.__aexit__ = AsyncMock(return_value=False)
        mock_engine.connect = MagicMock(return_value=mock_conn)
        
        with patch("src.routers.system.get_engine", return_value=mock_engine), \
             patch("src.routers.system.ai_service") as mock_ai:
            mock_ai.is_configured = False
            
            response = client.get("/system/health")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["services"]["ai"] == "not_configured"


class TestHealthzCheck:
    """Tests for GET /system/healthz endpoint."""

    def test_healthz_all_healthy(self, client):
        """Test extended health when all components are healthy."""
        mock_engine = MagicMock()
        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock()
        mock_conn.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_conn.__aexit__ = AsyncMock(return_value=False)
        mock_engine.connect = MagicMock(return_value=mock_conn)
        
        with patch("src.routers.system.get_engine", return_value=mock_engine), \
             patch("src.routers.system.ai_service") as mock_ai:
            mock_ai.is_configured = True
            mock_ai.is_available = True
            
            response = client.get("/system/healthz")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["components"]["database"] == "healthy"
        assert data["components"]["ai_service"] == "healthy"

    def test_healthz_db_unhealthy(self, client):
        """Test extended health when database is unhealthy."""
        with patch("src.routers.system.get_engine", side_effect=Exception("DB down")), \
             patch("src.routers.system.ai_service") as mock_ai:
            mock_ai.is_configured = False
            
            response = client.get("/system/healthz")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "degraded"
        assert data["components"]["database"] == "unhealthy"

    def test_healthz_ai_degraded(self, client):
        """Test extended health when AI is degraded."""
        mock_engine = MagicMock()
        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock()
        mock_conn.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_conn.__aexit__ = AsyncMock(return_value=False)
        mock_engine.connect = MagicMock(return_value=mock_conn)
        
        with patch("src.routers.system.get_engine", return_value=mock_engine), \
             patch("src.routers.system.ai_service") as mock_ai:
            mock_ai.is_configured = True
            mock_ai.is_available = False
            mock_ai.get_circuit_breaker_status.return_value = {
                "state": "open",
                "failure_count": 5
            }
            
            response = client.get("/system/healthz")
        
        assert response.status_code == 200
        data = response.json()
        assert data["components"]["ai_service"] == "degraded"
        assert "ai_circuit_breaker" in data


class TestReadinessCheck:
    """Tests for GET /system/ready endpoint."""

    def test_ready_when_db_available(self, client):
        """Test readiness when database is available."""
        mock_engine = MagicMock()
        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock()
        mock_conn.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_conn.__aexit__ = AsyncMock(return_value=False)
        mock_engine.connect = MagicMock(return_value=mock_conn)
        
        with patch("src.routers.system.get_engine", return_value=mock_engine):
            response = client.get("/system/ready")
        
        assert response.status_code == 200
        assert response.json() == {"status": "ready"}

    def test_not_ready_when_db_unavailable(self, client):
        """Test readiness when database is unavailable."""
        with patch("src.routers.system.get_engine", side_effect=Exception("DB unavailable")):
            response = client.get("/system/ready")
        
        assert response.status_code == 503
        assert "not ready" in response.json()["detail"].lower()


class TestMetricsEndpoint:
    """Tests for GET /system/metrics endpoint."""

    def test_metrics_returns_structure(self, client):
        """Test metrics endpoint returns correct structure."""
        with patch("src.routers.system.metrics") as mock_metrics:
            mock_metrics.get_metrics.return_value = {
                "total_tasks": 150,
                "successful_tasks": 142,
                "failed_tasks": 8,
                "avg_processing_time_ms": 3245.67,
                "ai_failures": 5
            }
            
            response = client.get("/system/metrics")
        
        assert response.status_code == 200
        data = response.json()
        assert "total_tasks" in data
        assert "successful_tasks" in data
        assert "failed_tasks" in data
        assert "avg_processing_time_ms" in data
        assert "ai_failures" in data

    def test_metrics_zero_values(self, client):
        """Test metrics with zero values."""
        with patch("src.routers.system.metrics") as mock_metrics:
            mock_metrics.get_metrics.return_value = {
                "total_tasks": 0,
                "successful_tasks": 0,
                "failed_tasks": 0,
                "avg_processing_time_ms": 0.0,
                "ai_failures": 0
            }
            
            response = client.get("/system/metrics")
        
        assert response.status_code == 200
        data = response.json()
        assert data["total_tasks"] == 0

    def test_metrics_high_values(self, client):
        """Test metrics with high load values."""
        with patch("src.routers.system.metrics") as mock_metrics:
            mock_metrics.get_metrics.return_value = {
                "total_tasks": 10000,
                "successful_tasks": 9500,
                "failed_tasks": 500,
                "avg_processing_time_ms": 5000.0,
                "ai_failures": 100
            }
            
            response = client.get("/system/metrics")

        assert response.status_code == 200
        data = response.json()
        assert data["total_tasks"] == 10000


class TestAIProvidersEndpoint:
    """Tests for GET /system/ai/providers endpoint."""

    def test_ai_providers_returns_default_and_available(self, client):
        with patch("src.routers.system.ai_service") as mock_ai:
            mock_ai.provider = "gigachat"
            mock_ai.available_providers = ["gigachat", "ollama"]

            response = client.get("/system/ai/providers")

        assert response.status_code == 200
        assert response.json() == {
            "default_provider": "gigachat",
            "available_providers": ["auto", "gigachat", "ollama"],
        }
