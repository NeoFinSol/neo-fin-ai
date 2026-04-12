from __future__ import annotations

import os

import src.routers.pdf_tasks as pdf_tasks
from src.analysis.extractor import semantics


class FakeAnalysis:
    def __init__(self, status: str, result: dict | None = None):
        self.status = status
        self.result = result
        self.cancel_requested_at = None


def test_upload_and_result(client, monkeypatch, tmp_path):
    """Test complete upload -> result flow."""
    store: dict[str, FakeAnalysis] = {}

    async def fake_create(task_id: str, status: str, result: dict | None = None):
        store[task_id] = FakeAnalysis(status=status, result=result)
        return store[task_id]

    async def fake_get(task_id: str):
        return store.get(task_id)

    async def fake_process(
        task_id: str,
        file_path: str,
        ai_provider: str | None = None,
        debug_trace: bool = False,
    ):
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


def test_upload_forwards_requested_ai_provider(client, monkeypatch, tmp_path):
    """Upload flow forwards requested ai_provider into the processing task."""
    store: dict[str, FakeAnalysis] = {}
    captured: dict[str, str | None] = {"provider": None}

    async def fake_create(task_id: str, status: str, result: dict | None = None):
        store[task_id] = FakeAnalysis(status=status, result=result)
        return store[task_id]

    async def fake_get(task_id: str):
        return store.get(task_id)

    async def fake_process(
        task_id: str,
        file_path: str,
        ai_provider: str | None = None,
        debug_trace: bool = False,
    ):
        captured["provider"] = ai_provider
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
        data={"ai_provider": "ollama"},
    )

    assert response.status_code == 200
    assert captured["provider"] == "ollama"


def test_result_returns_score_methodology(client, monkeypatch):
    """Completed result exposes scoring methodology in score payload."""

    analysis = FakeAnalysis(
        status="completed",
        result={
            "filename": "report.pdf",
            "data": {
                "ratios": {},
                "score": {
                    "score": 60.78,
                    "risk_level": "medium",
                    "confidence_score": 0.95,
                    "factors": [],
                    "normalized_scores": {},
                    "methodology": {
                        "benchmark_profile": "retail_demo",
                        "period_basis": "reported",
                        "detection_mode": "auto",
                        "reasons": ["retail_keyword"],
                        "guardrails": [],
                        "leverage_basis": "debt_only",
                        "ifrs16_adjusted": True,
                        "adjustments": [
                            "interest_coverage_sign_corrected",
                            "leverage_debt_only",
                        ],
                        "peer_context": [
                            "Large food retail may operate with current ratio below 1; Walmart current ratio ~0.79 (Jan 2026 reference).",
                        ],
                    },
                },
                "ai_runtime": {
                    "requested_provider": "ollama",
                    "effective_provider": "ollama",
                    "status": "succeeded",
                    "reason_code": None,
                },
            },
        },
    )

    async def fake_get(_task_id: str):
        return analysis

    monkeypatch.setattr(pdf_tasks, "get_analysis", fake_get)
    response = client.get("/result/task-with-methodology")

    assert response.status_code == 200
    payload = response.json()
    assert payload["data"]["score"]["methodology"]["benchmark_profile"] == "retail_demo"
    assert payload["data"]["score"]["methodology"]["period_basis"] == "reported"
    assert payload["data"]["score"]["methodology"]["leverage_basis"] == "debt_only"
    assert payload["data"]["score"]["methodology"]["ifrs16_adjusted"] is True
    assert (
        "leverage_debt_only" in payload["data"]["score"]["methodology"]["adjustments"]
    )
    assert payload["data"]["ai_runtime"]["effective_provider"] == "ollama"
    assert payload["data"]["ai_runtime"]["status"] == "succeeded"


def test_result_returns_v2_extraction_metadata_shape(client, monkeypatch):
    analysis = FakeAnalysis(
        status="completed",
        result={
            "filename": "report.pdf",
            "data": {
                "ratios": {},
                "score": {"score": 0},
                "extraction_metadata": {
                    "revenue": {
                        "evidence_version": "v2",
                        "confidence": 0.92,
                        "source": "table",
                        "match_semantics": "exact",
                        "inference_mode": "direct",
                        "postprocess_state": "none",
                        "reason_code": None,
                        "signal_flags": ["ev:line_code"],
                        "candidate_quality": 120,
                        "authoritative_override": False,
                    },
                    "ebitda": {
                        "evidence_version": "v2",
                        "confidence": 0.95,
                        "source": "issuer_fallback",
                        "match_semantics": "not_applicable",
                        "inference_mode": "policy_override",
                        "postprocess_state": "none",
                        "reason_code": semantics.REASON_ISSUER_REPO_OVERRIDE,
                        "signal_flags": [],
                        "candidate_quality": None,
                        "authoritative_override": True,
                    },
                },
            },
        },
    )

    async def fake_get(_task_id: str):
        return analysis

    monkeypatch.setattr(pdf_tasks, "get_analysis", fake_get)
    response = client.get("/result/task-with-v2-metadata")

    assert response.status_code == 200
    payload = response.json()
    assert payload["data"]["extraction_metadata"]["revenue"]["source"] == "table"
    assert (
        payload["data"]["extraction_metadata"]["revenue"]["match_semantics"] == "exact"
    )
    assert (
        payload["data"]["extraction_metadata"]["ebitda"]["authoritative_override"]
        is True
    )
