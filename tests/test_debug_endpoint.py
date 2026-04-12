from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import src.routers.debug as debug_router


def test_debug_trace_task_not_found(client, monkeypatch):
    mock = AsyncMock(return_value=None)
    monkeypatch.setattr(debug_router.crud, "get_analysis", mock)

    resp = client.get("/debug/decision-trace/nonexistent-task-id")
    assert resp.status_code == 404


def test_debug_trace_task_exists_no_trace(client, monkeypatch):
    mock_analysis = SimpleNamespace(result={"filename": "test.pdf"})
    mock = AsyncMock(return_value=mock_analysis)
    monkeypatch.setattr(debug_router.crud, "get_analysis", mock)

    resp = client.get("/debug/decision-trace/some-task-id")
    assert resp.status_code == 200
    data = resp.json()
    assert data["decision_trace"] is None


def test_debug_trace_task_exists_with_trace(client, monkeypatch):
    mock_analysis = SimpleNamespace(
        result={
            "decision_trace": {
                "per_metric": {},
                "pipeline": {"policy_name": "test"},
                "generated_at": "2026-04-12T18:31:00Z",
                "trace_version": "v1",
            }
        }
    )
    mock = AsyncMock(return_value=mock_analysis)
    monkeypatch.setattr(debug_router.crud, "get_analysis", mock)

    resp = client.get("/debug/decision-trace/some-task-id")
    assert resp.status_code == 200
    data = resp.json()
    assert data["decision_trace"] is not None
    assert data["decision_trace"]["trace_version"] == "v1"


def test_debug_trace_null_result(client, monkeypatch):
    mock_analysis = SimpleNamespace(result=None)
    mock = AsyncMock(return_value=mock_analysis)
    monkeypatch.setattr(debug_router.crud, "get_analysis", mock)

    resp = client.get("/debug/decision-trace/null-result-task")
    assert resp.status_code == 200
    data = resp.json()
    assert data["decision_trace"] is None
