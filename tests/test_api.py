from __future__ import annotations

import os

from fastapi.testclient import TestClient

import src.routers.pdf_tasks as pdf_tasks
from src.app import app


class FakeAnalysis:
    def __init__(self, status: str, result: dict | None = None):
        self.status = status
        self.result = result


def test_upload_and_result(monkeypatch, tmp_path):
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
