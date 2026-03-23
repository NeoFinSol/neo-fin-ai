from __future__ import annotations

import base64
import os

# Set DEV_MODE BEFORE importing app to bypass authentication in tests
os.environ["DEV_MODE"] = "1"

from io import BytesIO

from fastapi.testclient import TestClient

import src.routers.pdf_tasks as pdf_tasks
import src.routers.analyze as analyze_router
from src.app import app


class FakeAnalysis:
    def __init__(self, status: str, result: dict | None = None):
        self.status = status
        self.result = result


def test_upload_and_result(monkeypatch, tmp_path, dev_mode_enabled):
    store: dict[str, FakeAnalysis] = {}

    async def fake_create(task_id: str, status: str, result: dict | None = None):
        store[task_id] = FakeAnalysis(status=status, result=result)
        return store[task_id]

    async def fake_get(task_id: str):
        return store.get(task_id)

    async def fake_process(task_id: str, file_path: str):
        analysis = store.get(task_id)
        if analysis:
            analysis.status = "completed"
            analysis.result = {"data": {"ratios": {}, "score": {"score": 0}}}
        if os.path.exists(file_path):
            os.remove(file_path)

    monkeypatch.setattr(pdf_tasks, "create_analysis", fake_create)
    monkeypatch.setattr(pdf_tasks, "get_analysis", fake_get)
    monkeypatch.setattr(pdf_tasks, "process_pdf", fake_process)

    client = TestClient(app)

    pdf_path = tmp_path / "sample.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\n%EOF\n")

    response = client.post(
        "/upload",
        files={"file": ("sample.pdf", pdf_path.read_bytes(), "application/pdf")},
    )

    assert response.status_code == 200
    task_id = response.json().get("task_id")
    assert task_id

    result = client.get(f"/result/{task_id}")
    assert result.status_code == 200
    assert result.json()["status"] in {"processing", "completed"}


def test_result_not_found(monkeypatch):
    async def fake_get(_task_id: str):
        return None

    monkeypatch.setattr(pdf_tasks, "get_analysis", fake_get)

    client = TestClient(app)
    response = client.get("/result/unknown")

    assert response.status_code == 404


def test_analyze_pdf_file_success(monkeypatch, tmp_path):
    """Test /analyze/pdf/file endpoint with valid PDF."""
    
    async def fake_analyze(file_stream):
        return {
            "status": "completed",
            "data": {
                "scanned": False,
                "text": "Test text",
                "tables": [],
                "metrics": {},
                "ratios": {},
                "score": {"score": 75, "risk_level": "medium"},
            }
        }

    monkeypatch.setattr(analyze_router, "analyze_pdf", fake_analyze)

    client = TestClient(app)

    # Valid PDF with magic header
    pdf_content = b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog >>\nendobj\ntrailer\n<< /Root 1 0 R >>\n%%EOF\n"
    
    response = client.post(
        "/analyze/pdf/file",
        files={"file": ("test.pdf", pdf_content, "application/pdf")},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "completed"
    assert "data" in data
    assert data["data"]["score"]["score"] == 75


def test_analyze_pdf_file_invalid_content_type(monkeypatch):
    """Test /analyze/pdf/file with invalid content type."""
    client = TestClient(app)
    
    response = client.post(
        "/analyze/pdf/file",
        files={"file": ("test.txt", b"Hello World", "text/plain")},
    )

    assert response.status_code == 400
    assert "PDF file expected" in response.json()["detail"]


def test_analyze_pdf_file_empty_file(monkeypatch):
    """Test /analyze/pdf/file with empty file."""
    client = TestClient(app)
    
    response = client.post(
        "/analyze/pdf/file",
        files={"file": ("empty.pdf", b"", "application/pdf")},
    )

    assert response.status_code == 400
    assert "Empty file" in response.json()["detail"]


def test_analyze_pdf_file_invalid_format(monkeypatch):
    """Test /analyze/pdf/file with invalid PDF format (not a real PDF)."""
    client = TestClient(app)
    
    # Not a valid PDF (missing magic header)
    invalid_pdf = b"This is not a PDF file at all"
    
    response = client.post(
        "/analyze/pdf/file",
        files={"file": ("invalid.pdf", invalid_pdf, "application/pdf")},
    )

    assert response.status_code == 400
    assert "Invalid PDF file format" in response.json()["detail"]


def test_analyze_pdf_file_too_large(monkeypatch):
    """Test /analyze/pdf/file with file exceeding size limit."""
    client = TestClient(app)
    
    # Create a file larger than 50 MB
    large_pdf = b"%PDF-1.4\n" + (b"x" * (51 * 1024 * 1024))
    
    response = client.post(
        "/analyze/pdf/file",
        files={"file": ("large.pdf", large_pdf, "application/pdf")},
    )

    assert response.status_code == 400
    assert "File too large" in response.json()["detail"]


def test_analyze_pdf_base64_success(monkeypatch):
    """Test /analyze/pdf/base64 endpoint with valid base64 PDF."""
    
    async def fake_analyze(file_stream):
        return {
            "status": "completed",
            "data": {
                "scanned": False,
                "text": "Base64 test",
                "tables": [],
                "metrics": {},
                "ratios": {},
                "score": {"score": 80, "risk_level": "low"},
            }
        }

    monkeypatch.setattr(analyze_router, "analyze_pdf", fake_analyze)

    client = TestClient(app)

    # Valid PDF encoded as base64
    pdf_content = b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog >>\nendobj\ntrailer\n<< /Root 1 0 R >>\n%%EOF\n"
    base64_data = base64.b64encode(pdf_content).decode("utf-8")

    response = client.post(
        "/analyze/pdf/base64",
        json={"file_data": base64_data},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "completed"
    assert data["data"]["score"]["score"] == 80


def test_analyze_pdf_base64_invalid_base64(monkeypatch):
    """Test /analyze/pdf/base64 with invalid base64 string."""
    client = TestClient(app)
    
    response = client.post(
        "/analyze/pdf/base64",
        json={"file_data": "!!!invalid_base64!!!"},
    )

    assert response.status_code == 400
    assert "Failed to decode base64" in response.json()["detail"]


def test_analyze_pdf_base64_empty_data(monkeypatch):
    """Test /analyze/pdf/base64 with empty base64 data."""
    client = TestClient(app)
    
    # Empty string encoded as base64
    base64_data = base64.b64encode(b"").decode("utf-8")
    
    response = client.post(
        "/analyze/pdf/base64",
        json={"file_data": base64_data},
    )

    assert response.status_code == 400
    assert "Empty decoded data" in response.json()["detail"]


def test_analyze_pdf_base64_invalid_format(monkeypatch):
    """Test /analyze/pdf/base64 with valid base64 but invalid PDF."""
    client = TestClient(app)
    
    # Encode non-PDF content as base64
    invalid_content = b"This is not a PDF"
    base64_data = base64.b64encode(invalid_content).decode("utf-8")
    
    response = client.post(
        "/analyze/pdf/base64",
        json={"file_data": base64_data},
    )

    assert response.status_code == 400
    assert "Invalid PDF file format" in response.json()["detail"]


def test_analyze_pdf_base64_too_large(monkeypatch):
    """Test /analyze/pdf/base64 with data exceeding size limit."""
    client = TestClient(app)
    
    # Create large content and encode as base64
    large_content = b"%PDF-1.4\n" + (b"x" * (51 * 1024 * 1024))
    base64_data = base64.b64encode(large_content).decode("utf-8")
    
    response = client.post(
        "/analyze/pdf/base64",
        json={"file_data": base64_data},
    )

    assert response.status_code == 400
    assert "File too large" in response.json()["detail"]


def test_analyze_pdf_file_error_handling(monkeypatch, dev_mode_enabled):
    """Test error handling in /analyze/pdf/file endpoint."""

    async def fake_analyze_error(file_stream):
        raise Exception("Internal processing error")

    monkeypatch.setattr(analyze_router, "analyze_pdf", fake_analyze_error)

    client = TestClient(app)

    pdf_content = b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog >>\nendobj\ntrailer\n<< /Root 1 0 R >>\n%%EOF\n"

    response = client.post(
        "/analyze/pdf/file",
        files={"file": ("test.pdf", pdf_content, "application/pdf")},
    )

    assert response.status_code == 500
    assert "Internal server error" in response.json()["detail"]


def test_analyze_pdf_base64_error_handling(monkeypatch, dev_mode_enabled):
    """Test error handling in /analyze/pdf/base64 endpoint."""

    async def fake_analyze_error(file_stream):
        raise ValueError("Some processing error")

    monkeypatch.setattr(analyze_router, "analyze_pdf", fake_analyze_error)

    client = TestClient(app)

    pdf_content = b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog >>\nendobj\ntrailer\n<< /Root 1 0 R >>\n%%EOF\n"
    base64_data = base64.b64encode(pdf_content).decode("utf-8")

    response = client.post(
        "/analyze/pdf/base64",
        json={"file_data": base64_data},
    )

    assert response.status_code == 500
    assert "Internal server error" in response.json()["detail"]
