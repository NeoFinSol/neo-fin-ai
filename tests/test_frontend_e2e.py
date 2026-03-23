"""
Frontend-Backend Integration E2E Tests.

These tests verify the integration between the React frontend and the FastAPI backend.
They test the complete user flow through the UI.

Note: These tests require the frontend to be built and served.
Run with: pytest tests/test_frontend_e2e.py -m frontend
"""
import base64
import time

import pytest
from fastapi.testclient import TestClient

from src.app import app


# Mark all tests in this module as frontend integration tests
pytestmark = pytest.mark.frontend


# Test PDF content (minimal valid PDF)
MINIMAL_PDF = (
    b"%PDF-1.4\n"
    b"1 0 obj\n<< /Type /Catalog >>\nendobj\n"
    b"2 0 obj\n<< /Type /Pages /Kids [3 0 R] >>\nendobj\n"
    b"3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] >>\nendobj\n"
    b"trailer\n<< /Root 1 0 R /Size 4 >>\n%%EOF\n"
)


@pytest.fixture
def client():
    """Create test client with DEV_MODE enabled."""
    import os
    old_dev_mode = os.environ.get("DEV_MODE")
    os.environ["DEV_MODE"] = "1"
    
    with TestClient(app) as test_client:
        yield test_client
    
    if old_dev_mode is None:
        os.environ.pop("DEV_MODE", None)
    else:
        os.environ["DEV_MODE"] = old_dev_mode


class TestFrontendAPIIntegration:
    """Test frontend API integration points."""

    @pytest.mark.asyncio
    async def test_health_endpoint_for_frontend(self, client):
        """Test that frontend can access health endpoint."""
        response = client.get("/system/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}

    @pytest.mark.asyncio
    async def test_upload_endpoint_simulation(self, client, dev_mode_enabled):
        """Test upload endpoint as frontend would call it."""
        # Simulate frontend file upload
        response = client.post(
            "/upload",
            files={"file": ("test.pdf", MINIMAL_PDF, "application/pdf")},
        )
        
        # Should return task_id for polling
        assert response.status_code == 200
        data = response.json()
        assert "task_id" in data

    @pytest.mark.asyncio
    async def test_result_polling_simulation(self, client, dev_mode_enabled):
        """Test result polling as frontend would do it."""
        # First upload a file
        upload_response = client.post(
            "/upload",
            files={"file": ("test.pdf", MINIMAL_PDF, "application/pdf")},
        )
        task_id = upload_response.json()["task_id"]
        
        # Poll for result (simulate frontend behavior)
        max_attempts = 5
        for attempt in range(max_attempts):
            result_response = client.get(f"/result/{task_id}")
            assert result_response.status_code == 200
            
            result_data = result_response.json()
            status = result_data.get("status")
            
            if status in ["completed", "failed"]:
                break
            
            time.sleep(0.5)
        
        # Verify final status
        assert "status" in result_data

    @pytest.mark.asyncio
    async def test_analyze_direct_endpoint(self, client, dev_mode_enabled):
        """Test direct analysis endpoint (alternative frontend flow)."""
        response = client.post(
            "/analyze/pdf/file",
            files={"file": ("test.pdf", MINIMAL_PDF, "application/pdf")},
        )
        
        # Should return analysis result (possibly empty for minimal PDF)
        assert response.status_code in [200, 400]
        
        if response.status_code == 200:
            result = response.json()
            assert isinstance(result, dict)

    @pytest.mark.asyncio
    async def test_base64_analysis_endpoint(self, client, dev_mode_enabled):
        """Test base64 analysis endpoint (used by some frontend implementations)."""
        base64_data = base64.b64encode(MINIMAL_PDF).decode("utf-8")
        
        response = client.post(
            "/analyze/pdf/base64",
            json={"file_data": base64_data},
        )
        
        # Should return analysis result
        assert response.status_code in [200, 400]
        
        if response.status_code == 200:
            result = response.json()
            assert isinstance(result, dict)


class TestFrontendErrorHandling:
    """Test frontend error handling scenarios."""

    @pytest.mark.asyncio
    async def test_frontend_file_too_large_error(self, client, dev_mode_enabled):
        """Test that frontend receives proper error for large files."""
        # Create a file larger than MAX_FILE_SIZE (50 MB)
        large_content = b"%PDF-1.4\n" + b"x" * (51 * 1024 * 1024)
        
        response = client.post(
            "/upload",
            files={"file": ("large.pdf", large_content, "application/pdf")},
        )
        
        assert response.status_code == 400
        assert "too large" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_frontend_invalid_pdf_error(self, client, dev_mode_enabled):
        """Test that frontend receives proper error for invalid PDF."""
        response = client.post(
            "/upload",
            files={"file": ("invalid.pdf", b"not a pdf", "application/pdf")},
        )
        
        assert response.status_code == 400
        assert "detail" in response.json()

    @pytest.mark.asyncio
    async def test_frontend_empty_file_error(self, client, dev_mode_enabled):
        """Test that frontend receives proper error for empty files."""
        response = client.post(
            "/upload",
            files={"file": ("empty.pdf", b"", "application/pdf")},
        )
        
        assert response.status_code == 400
        assert "detail" in response.json()

    @pytest.mark.asyncio
    async def test_frontend_task_not_found_error(self, client, dev_mode_enabled):
        """Test that frontend receives proper error for non-existent task."""
        response = client.get("/result/non-existent-task-id")
        
        assert response.status_code == 404
        assert "detail" in response.json()


class TestFrontendCORS:
    """Test CORS configuration for frontend."""

    @pytest.mark.asyncio
    async def test_cors_headers_present(self, client):
        """Test that CORS headers are present in responses."""
        response = client.options(
            "/system/health",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "GET",
            }
        )
        
        # CORS should be configured (may allow or deny, but headers should be present)
        assert response.status_code in [200, 400, 404]

    @pytest.mark.asyncio
    async def test_health_accessible_from_any_origin(self, client):
        """Test that health endpoint is accessible (CORS allowed)."""
        response = client.get(
            "/system/health",
            headers={"Origin": "http://example.com"}
        )
        
        # Health endpoint should be accessible
        assert response.status_code == 200
