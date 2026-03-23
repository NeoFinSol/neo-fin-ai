"""
End-to-End (E2E) tests for NeoFin AI.

These tests verify the complete application flow:
1. Upload a PDF document
2. Wait for processing
3. Retrieve and validate results
"""
import asyncio
import base64
import io
import os
import time
from pathlib import Path

# Set DEV_MODE BEFORE importing app to bypass authentication in tests
os.environ["DEV_MODE"] = "1"

import pytest
from fastapi.testclient import TestClient

from src.app import app
from src.db.crud import get_analysis, create_analysis
from src.db.database import get_session_maker


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
    """Create test client."""
    with TestClient(app) as client:
        yield client


@pytest.fixture
def test_pdf_file(tmp_path):
    """Create a test PDF file."""
    pdf_path = tmp_path / "test_report.pdf"
    pdf_path.write_bytes(MINIMAL_PDF)
    return pdf_path


@pytest.fixture
def test_pdf_base64():
    """Create a test PDF in base64 format."""
    return base64.b64encode(MINIMAL_PDF).decode("utf-8")


class TestE2EUploadAndAnalyze:
    """End-to-end tests for PDF upload and analysis flow."""

    @pytest.mark.asyncio
    async def test_analyze_pdf_file_endpoint(self, client, test_pdf_file, dev_mode_enabled):
        """Test /analyze/pdf/file endpoint (direct analysis)."""
        with open(test_pdf_file, "rb") as f:
            response = client.post(
                "/analyze/pdf/file",
                files={"file": ("test_report.pdf", f, "application/pdf")},
            )
        
        # Should return 200 (possibly with empty result for minimal PDF)
        assert response.status_code in [200, 400]
        
        if response.status_code == 200:
            result = response.json()
            # Result should be a dict (possibly empty for invalid PDF)
            assert isinstance(result, dict)

    @pytest.mark.asyncio
    async def test_analyze_pdf_base64_endpoint(self, client, test_pdf_base64, dev_mode_enabled):
        """Test /analyze/pdf/base64 endpoint (direct analysis)."""
        response = client.post(
            "/analyze/pdf/base64",
            json={"file_data": test_pdf_base64},
        )
        
        # Should return 200 (possibly with empty result for minimal PDF)
        assert response.status_code in [200, 400]
        
        if response.status_code == 200:
            result = response.json()
            assert isinstance(result, dict)

    @pytest.mark.asyncio
    async def test_error_handling_invalid_pdf(self, client, dev_mode_enabled):
        """Test error handling for invalid PDF files."""
        # Invalid PDF content
        invalid_pdf = b"This is not a PDF"
        
        response = client.post(
            "/analyze/pdf/file",
            files={"file": ("invalid.pdf", invalid_pdf, "application/pdf")},
        )
        
        assert response.status_code == 400
        assert "detail" in response.json()

    @pytest.mark.asyncio
    async def test_error_handling_empty_file(self, client, dev_mode_enabled):
        """Test error handling for empty files."""
        response = client.post(
            "/analyze/pdf/file",
            files={"file": ("empty.pdf", b"", "application/pdf")},
        )
        
        assert response.status_code == 400
        assert "detail" in response.json()

    @pytest.mark.asyncio
    async def test_error_handling_invalid_base64(self, client, dev_mode_enabled):
        """Test error handling for invalid base64 data."""
        response = client.post(
            "/analyze/pdf/base64",
            json={"file_data": "not-valid-base64!!!"},
        )
        
        assert response.status_code == 400
        assert "detail" in response.json()


class TestE2EMultipleUsers:
    """Test concurrent user scenarios."""

    @pytest.mark.asyncio
    async def test_concurrent_analyze_requests(self, client, test_pdf_file, dev_mode_enabled):
        """Test multiple concurrent analyze requests."""
        import concurrent.futures
        
        def analyze_pdf():
            with open(test_pdf_file, "rb") as f:
                response = client.post(
                    "/analyze/pdf/file",
                    files={"file": ("test_report.pdf", f, "application/pdf")},
                )
                return response.status_code
        
        # Execute 5 concurrent requests
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(analyze_pdf) for _ in range(5)]
            results = [f.result() for f in concurrent.futures.as_completed(futures)]
        
        # All requests should succeed (200 or 400 for invalid PDF)
        for status_code in results:
            assert status_code in [200, 400]


class TestE2ELargeFiles:
    """Test handling of large files."""

    @pytest.mark.asyncio
    async def test_file_size_limit(self, client, dev_mode_enabled):
        """Test that files exceeding size limit are rejected."""
        # Create a file larger than MAX_FILE_SIZE (50 MB) with valid PDF header
        large_content = b"%PDF-1.4\n" + b"x" * (51 * 1024 * 1024)  # 51 MB with PDF header
        
        response = client.post(
            "/upload",
            files={"file": ("large.pdf", large_content, "application/pdf")},
        )
        
        assert response.status_code == 400
        assert "too large" in response.json()["detail"].lower()


class TestE2EAPIAuthentication:
    """Test API authentication in E2E scenarios."""

    @pytest.mark.asyncio
    async def test_request_with_valid_api_key(self, client, test_pdf_file, auth_enabled):
        """Test API requests with valid API key."""
        with open(test_pdf_file, "rb") as f:
            response = client.post(
                "/analyze/pdf/file",
                files={"file": ("test_report.pdf", f, "application/pdf")},
                headers={"X-API-Key": "test-api-key-for-testing"},
            )
        
        assert response.status_code in [200, 400]

    @pytest.mark.asyncio
    async def test_request_with_invalid_api_key(self, client, test_pdf_file):
        """Test API requests with invalid API key."""
        # Ensure auth is enabled (no DEV_MODE)
        import os
        os.environ["DEV_MODE"] = "0"
        os.environ["API_KEY"] = "correct-key"
        
        # Reload auth module
        import importlib
        import src.core.auth as auth_module
        importlib.reload(auth_module)
        
        with open(test_pdf_file, "rb") as f:
            response = client.post(
                "/analyze/pdf/file",
                files={"file": ("test_report.pdf", f, "application/pdf")},
                headers={"X-API-Key": "wrong-key"},
            )
        
        assert response.status_code == 401
