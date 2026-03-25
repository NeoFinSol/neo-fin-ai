"""
End-to-End (E2E) tests for NeoFin AI.
"""
import asyncio
import base64
import io
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from src.db.crud import get_analysis, create_analysis
from src.db.database import get_session_maker


# Mark all tests in this module as e2e
pytestmark = pytest.mark.e2e


# Test PDF content (minimal valid PDF)
MINIMAL_PDF = (
    b"%PDF-1.4\n"
    b"1 0 obj\n<< /Type /Catalog >>\nendobj\n"
    b"2 0 obj\n<< /Type /Pages /Kids [3 0 R] >>\nendobj\n"
    b"3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] >>\nendobj\n"
    b"trailer\n<< /Root 1 0 R /Size 4 >>\n%%EOF\n"
)


@pytest.fixture
def test_pdf_file(tmp_path):
    """Create a test PDF file."""
    pdf_path = tmp_path / "test_report.pdf"
    pdf_path.write_bytes(MINIMAL_PDF)
    return pdf_path


@pytest.fixture
def test_base64_pdf():
    """Create a test base64 PDF."""
    return base64.b64encode(MINIMAL_PDF).decode()


class TestE2EUploadAndAnalyze:
    """E2E tests for upload and analyze flow."""

    def test_upload_and_get_result(self, client, tmp_path):
        """Test complete upload → processing → result flow."""
        pdf_path = tmp_path / "test.pdf"
        pdf_path.write_bytes(MINIMAL_PDF)

        # Upload
        response = client.post(
            "/upload",
            files={"file": ("test.pdf", pdf_path.read_bytes(), "application/pdf")},
        )
        assert response.status_code == 200
        task_id = response.json()["task_id"]
        assert task_id

        # Poll for result
        for _ in range(10):
            result = client.get(f"/result/{task_id}")
            assert result.status_code == 200
            data = result.json()
            if data.get("status") == "completed":
                break
            time.sleep(0.5)
        else:
            pytest.fail("Task did not complete in time")

    def test_error_handling_empty_file(self, client, tmp_path):
        """Test error handling for empty file."""
        pdf_path = tmp_path / "empty.pdf"
        pdf_path.write_bytes(b"")

        response = client.post(
            "/upload",
            files={"file": ("empty.pdf", pdf_path.read_bytes(), "application/pdf")},
        )

        assert response.status_code == 400

    def test_base64_success(self, client, test_base64_pdf):
        """Test successful base64 analysis."""
        response = client.post(
            "/analyze/pdf/base64",
            json={"data": test_base64_pdf},
        )

        assert response.status_code == 200
        assert "task_id" in response.json()
