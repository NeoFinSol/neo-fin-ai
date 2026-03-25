"""
Frontend integration tests.
"""
import pytest
from fastapi.testclient import TestClient


pytestmark = pytest.mark.frontend


class TestFrontendErrorHandling:
    """Test frontend error handling scenarios."""

    def test_frontend_file_too_large_error(self, client, tmp_path):
        """Test frontend receives proper error for large file."""
        large_content = b"x" * 60 * 1024 * 1024  # 60MB
        
        response = client.post(
            "/upload",
            files={"file": ("large.pdf", large_content, "application/pdf")},
        )

        # Should return 400 (either size or format error)
        assert response.status_code == 400
        assert "detail" in response.json()

    def test_frontend_empty_file_error(self, client, tmp_path):
        """Test frontend receives proper error for empty file."""
        pdf_path = tmp_path / "empty.pdf"
        pdf_path.write_bytes(b"")

        response = client.post(
            "/upload",
            files={"file": ("empty.pdf", pdf_path.read_bytes(), "application/pdf")},
        )

        assert response.status_code == 400

    def test_frontend_task_not_found_error(self, client):
        """Test frontend receives 404 for unknown task."""
        response = client.get("/result/nonexistent-task-id")

        assert response.status_code == 404


class TestFrontendSuccessPaths:
    """Test frontend success scenarios."""

    def test_frontend_upload_success(self, client, tmp_path):
        """Test frontend receives task_id on successful upload."""
        pdf_path = tmp_path / "test.pdf"
        pdf_path.write_bytes(b"%PDF-1.4\n%EOF\n")

        response = client.post(
            "/upload",
            files={"file": ("test.pdf", pdf_path.read_bytes(), "application/pdf")},
        )

        assert response.status_code == 200
        assert "task_id" in response.json()

    def test_frontend_result_polling(self, client, tmp_path):
        """Test frontend can poll for results."""
        pdf_path = tmp_path / "test.pdf"
        pdf_path.write_bytes(b"%PDF-1.4\n%EOF\n")

        # Upload
        response = client.post(
            "/upload",
            files={"file": ("test.pdf", pdf_path.read_bytes(), "application/pdf")},
        )
        task_id = response.json()["task_id"]

        # Poll
        response = client.get(f"/result/{task_id}")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
