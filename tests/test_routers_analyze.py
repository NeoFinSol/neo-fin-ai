"""
Tests for routers/analyze.py endpoints.
"""
import base64
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient


class TestAnalyzePdfFile:
    """Tests for POST /analyze/pdf/file endpoint."""

    def test_analyze_pdf_file_success(self, client, tmp_path, monkeypatch):
        """Test successful PDF file analysis."""
        from src.controllers import analyze as analyze_controller
        
        async def fake_analyze(file, task_id=None):
            return {"status": "completed", "data": {"score": {"score": 75}}}

        monkeypatch.setattr(analyze_controller, "analyze_pdf", fake_analyze)

        pdf_path = tmp_path / "test.pdf"
        pdf_path.write_bytes(b"%PDF-1.4\n%EOF\n")

        response = client.post(
            "/analyze/pdf/file",
            files={"file": ("test.pdf", pdf_path.read_bytes(), "application/pdf")},
        )

        assert response.status_code == 200

    def test_analyze_pdf_file_invalid_content_type(self, client, tmp_path):
        """Test rejection of non-PDF file."""
        pdf_path = tmp_path / "test.txt"
        pdf_path.write_bytes(b"not a pdf")

        response = client.post(
            "/analyze/pdf/file",
            files={"file": ("test.txt", pdf_path.read_bytes(), "text/plain")},
        )

        assert response.status_code == 400

    def test_analyze_pdf_file_too_large(self, client, tmp_path, monkeypatch):
        """Test rejection of oversized file."""
        monkeypatch.setenv("MAX_FILE_SIZE", "100")

        large_content = b"x" * 1000

        response = client.post(
            "/analyze/pdf/file",
            files={"file": ("large.pdf", large_content, "application/pdf")},
        )

        assert response.status_code == 400


class TestAnalyzePdfBase64:
    """Tests for POST /analyze/pdf/base64 endpoint."""

    def test_analyze_pdf_base64_success(self, client, monkeypatch):
        """Test successful base64 PDF analysis."""
        from src.controllers import analyze as analyze_controller
        
        pdf_content = b"%PDF-1.4 test"
        base64_data = base64.b64encode(pdf_content).decode()

        async def fake_analyze(file, task_id=None):
            return {"status": "completed", "data": {"score": {"score": 75}}}

        monkeypatch.setattr(analyze_controller, "analyze_pdf", fake_analyze)

        response = client.post("/analyze/pdf/base64", json={"file_data": base64_data})

        assert response.status_code == 200

    def test_analyze_pdf_base64_empty_data(self, client):
        """Test rejection of empty base64 data."""
        response = client.post("/analyze/pdf/base64", json={"file_data": ""})

        assert response.status_code == 400

    def test_analyze_pdf_base64_invalid_base64(self, client):
        """Test rejection of invalid base64."""
        response = client.post("/analyze/pdf/base64", json={"file_data": "not-valid!!!"})

        assert response.status_code == 400

    def test_analyze_pdf_base64_missing_data(self, client):
        """Test rejection of missing data field."""
        response = client.post("/analyze/pdf/base64", json={})

        assert response.status_code == 422
