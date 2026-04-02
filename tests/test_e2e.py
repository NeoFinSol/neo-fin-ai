"""
End-to-End (E2E) tests for NeoFin AI.
"""
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


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


class TestE2EUploadAndAnalyze:
    """E2E tests for upload and analyze flow."""

    def test_upload_and_get_result(self, client, tmp_path):
        """Test complete upload → processing → result flow."""
        pdf_path = tmp_path / "test.pdf"
        pdf_path.write_bytes(MINIMAL_PDF)

        processing_analysis = MagicMock(
            status="processing",
            result=None,
            cancel_requested_at=None,
            cancelled_at=None,
        )
        completed_analysis = MagicMock(
            status="completed",
            result={"data": {"score": {"score": 88.0}}},
            cancel_requested_at=None,
            cancelled_at=None,
        )

        with patch("src.routers.pdf_tasks.create_analysis", new_callable=AsyncMock), \
             patch("src.routers.pdf_tasks.dispatch_pdf_task", new_callable=AsyncMock), \
             patch(
                 "src.routers.pdf_tasks.get_analysis",
                 new_callable=AsyncMock,
                 side_effect=[processing_analysis, completed_analysis],
             ):
            response = client.post(
                "/upload",
                files={"file": ("test.pdf", pdf_path.read_bytes(), "application/pdf")},
            )
            assert response.status_code == 200
            task_id = response.json()["task_id"]
            assert task_id

            for _ in range(10):
                result = client.get(f"/result/{task_id}")
                assert result.status_code == 200
                data = result.json()
                if data.get("status") == "completed":
                    break
                time.sleep(0.01)
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

    def test_result_not_found_returns_404(self, client):
        """Unknown task id should return 404 on the current API surface."""
        with patch(
            "src.routers.pdf_tasks.get_analysis",
            new_callable=AsyncMock,
            return_value=None,
        ):
            response = client.get("/result/nonexistent-task-id")
        assert response.status_code == 404
