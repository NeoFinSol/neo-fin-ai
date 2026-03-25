from __future__ import annotations

import base64
import os

from io import BytesIO

import pytest

import src.routers.pdf_tasks as pdf_tasks
import src.routers.analyze as analyze_router
from src.controllers import analyze as analyze_controller


class FakeAnalysis:
    def __init__(self, status: str, result: dict | None = None):
        self.status = status
        self.result = result


def test_upload_and_result(client, monkeypatch, tmp_path):
    """Test complete upload → result flow."""
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


def test_result_not_found(client, monkeypatch):
    """Test 404 for unknown task_id."""
    async def fake_get(_task_id: str):
        return None

    monkeypatch.setattr(pdf_tasks, "get_analysis", fake_get)
    response = client.get("/result/unknown")

    assert response.status_code == 404


def test_analyze_pdf_file_success(client, monkeypatch, tmp_path):
    """Test /analyze/pdf/file endpoint with valid PDF."""
    async def fake_analyze(file, task_id=None):
        return {"status": "completed", "data": {"ratios": {}, "score": {"score": 75}}}

    monkeypatch.setattr(analyze_controller, "analyze_pdf", fake_analyze)

    pdf_path = tmp_path / "test.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\n%EOF\n")

    response = client.post(
        "/analyze/pdf/file",
        files={"file": ("test.pdf", pdf_path.read_bytes(), "application/pdf")},
    )

    assert response.status_code == 200


def test_analyze_pdf_file_invalid_content_type(client, tmp_path):
    """Test rejection of non-PDF file."""
    pdf_path = tmp_path / "test.txt"
    pdf_path.write_bytes(b"not a pdf")

    response = client.post(
        "/analyze/pdf/file",
        files={"file": ("test.txt", pdf_path.read_bytes(), "text/plain")},
    )

    assert response.status_code == 400


def test_analyze_pdf_file_empty_file(client, tmp_path):
    """Test rejection of empty file."""
    pdf_path = tmp_path / "empty.pdf"
    pdf_path.write_bytes(b"")

    response = client.post(
        "/analyze/pdf/file",
        files={"file": ("empty.pdf", pdf_path.read_bytes(), "application/pdf")},
    )

    assert response.status_code == 400


def test_analyze_pdf_file_too_large(client, tmp_path, monkeypatch):
    """Test rejection of oversized file."""
    monkeypatch.setenv("MAX_FILE_SIZE", "100")
    
    large_content = b"x" * 1000
    
    response = client.post(
        "/analyze/pdf/file",
        files={"file": ("large.pdf", large_content, "application/pdf")},
    )

    assert response.status_code == 400


def test_analyze_pdf_base64_success(client, monkeypatch):
    """Test /analyze/pdf/base64 with valid data."""
    pdf_content = b"%PDF-1.4 test"
    base64_data = base64.b64encode(pdf_content).decode()

    async def fake_analyze(file, task_id=None):
        return {"status": "completed", "data": {"ratios": {}, "score": {"score": 75}}}

    monkeypatch.setattr(analyze_controller, "analyze_pdf", fake_analyze)

    response = client.post("/analyze/pdf/base64", json={"file_data": base64_data})

    assert response.status_code == 200


def test_analyze_pdf_base64_invalid_base64(client):
    """Test rejection of invalid base64."""
    response = client.post("/analyze/pdf/base64", json={"file_data": "not-valid!!!"})

    assert response.status_code == 400


def test_analyze_pdf_base64_empty_data(client):
    """Test rejection of empty base64 data."""
    response = client.post("/analyze/pdf/base64", json={"file_data": ""})

    assert response.status_code == 400


def test_analyze_pdf_base64_missing_data(client):
    """Test rejection of missing data field."""
    response = client.post("/analyze/pdf/base64", json={})

    assert response.status_code == 422
