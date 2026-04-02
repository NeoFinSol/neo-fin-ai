"""
Unit tests for GET /analyses and GET /analyses/{task_id} router.
Feature: analysis-history-visualization
Requirements: 1.6, 1.7, 2.3, 2.4
"""
from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy.exc import SQLAlchemyError

from src.app import app
from src.core.auth import get_api_key
from src.exceptions import DatabaseError
from src.routers.analyses import get_analysis_detail

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

VALID_API_KEY = "test-secret-key"


def _mock_analysis(task_id: str = "abc-123") -> MagicMock:
    obj = MagicMock()
    obj.task_id = task_id
    obj.status = "completed"
    obj.created_at = datetime(2024, 1, 15, 12, 0, 0, tzinfo=timezone.utc)
    obj.score = None
    obj.risk_level = None
    obj.filename = None
    obj.result = {
        "filename": "report.pdf",
        "data": {
            "score": {"score": 72.5, "risk_level": "medium", "factors": [], "normalized_scores": {}},
            "metrics": {},
            "ratios": {},
        },
    }
    return obj


async def _auth_ok():
    return VALID_API_KEY


async def _auth_deny():
    raise HTTPException(status_code=401, detail="Missing API key. Provide it via X-API-Key header.")


# ---------------------------------------------------------------------------
# Auth tests — override get_api_key dependency to raise 401
# Requirements: 1.6, 2.4
# ---------------------------------------------------------------------------

class TestAnalysesAuth:
    """Missing API key → 401."""

    def test_list_without_api_key_returns_401(self):
        app.dependency_overrides[get_api_key] = _auth_deny
        try:
            with patch("src.routers.analyses.get_analyses_list", new_callable=AsyncMock, return_value=([], 0)):
                with TestClient(app, raise_server_exceptions=False) as client:
                    response = client.get("/analyses")
        finally:
            app.dependency_overrides.pop(get_api_key, None)
        assert response.status_code == 401

    def test_detail_without_api_key_returns_401(self):
        app.dependency_overrides[get_api_key] = _auth_deny
        try:
            with patch("src.routers.analyses.get_analysis", new_callable=AsyncMock, return_value=None):
                with TestClient(app, raise_server_exceptions=False) as client:
                    response = client.get("/analyses/some-task-id")
        finally:
            app.dependency_overrides.pop(get_api_key, None)
        assert response.status_code == 401


# ---------------------------------------------------------------------------
# 404 test — override auth to pass, mock CRUD to return None
# Requirement: 2.3
# ---------------------------------------------------------------------------

class TestAnalysesDetail:
    """Unknown task_id → 404."""

    def test_unknown_task_id_returns_404(self):
        app.dependency_overrides[get_api_key] = _auth_ok
        try:
            with patch("src.routers.analyses.get_analysis", new_callable=AsyncMock, return_value=None):
                with TestClient(app) as client:
                    response = client.get("/analyses/nonexistent-id")
        finally:
            app.dependency_overrides.pop(get_api_key, None)

        assert response.status_code == 404
        assert response.json()["detail"] == "Analysis not found"

    @pytest.mark.asyncio
    async def test_db_failure_raises_database_error(self):
        with patch(
            "src.routers.analyses.get_analysis",
            new_callable=AsyncMock,
            side_effect=SQLAlchemyError("db down"),
        ):
            with pytest.raises(DatabaseError):
                await get_analysis_detail("broken-task-id", _api_key=VALID_API_KEY)


class TestAnalysesTypedSummaryFallback:
    """Typed DB summary columns should be used when available."""

    def test_list_prefers_typed_summary_columns(self):
        analysis = _mock_analysis()
        analysis.score = 88.0
        analysis.risk_level = "low"
        analysis.filename = "typed.pdf"
        analysis.result = {"filename": "old.pdf", "data": {"score": {"score": 11.0, "risk_level": "high"}}}

        app.dependency_overrides[get_api_key] = _auth_ok
        try:
            with patch(
                "src.routers.analyses.get_analyses_list",
                new_callable=AsyncMock,
                return_value=([analysis], 1),
            ):
                with TestClient(app) as client:
                    response = client.get("/analyses?page=1&page_size=20")
        finally:
            app.dependency_overrides.pop(get_api_key, None)

        assert response.status_code == 200
        item = response.json()["items"][0]
        assert item["score"] == 88.0
        assert item["risk_level"] == "low"
        assert item["filename"] == "typed.pdf"


# ---------------------------------------------------------------------------
# Validation tests — FastAPI rejects bad query params before calling endpoint
# Requirements: 1.6, 1.7
# ---------------------------------------------------------------------------

class TestAnalysesValidation:
    """Invalid query params → 422."""

    def test_page_non_integer_returns_422(self):
        app.dependency_overrides[get_api_key] = _auth_ok
        try:
            with TestClient(app) as client:
                response = client.get("/analyses?page=abc")
        finally:
            app.dependency_overrides.pop(get_api_key, None)
        assert response.status_code == 422

    def test_page_size_over_100_returns_422(self):
        app.dependency_overrides[get_api_key] = _auth_ok
        try:
            with TestClient(app) as client:
                response = client.get("/analyses?page_size=101")
        finally:
            app.dependency_overrides.pop(get_api_key, None)
        assert response.status_code == 422

# ---------------------------------------------------------------------------
# Property 1: Структура ответа GET /analyses
# Feature: analysis-history-visualization, Property 1: структура ответа GET /analyses
# Validates: Requirements 1.2, 1.4
# ---------------------------------------------------------------------------

import uuid

from hypothesis import given, settings
from hypothesis import strategies as st


def _analysis_strategy():
    """Hypothesis strategy producing mock Analysis ORM objects."""
    return st.builds(
        lambda tid, score, risk, filename: _build_mock(tid, score, risk, filename),
        tid=st.uuids().map(str),
        score=st.one_of(st.none(), st.floats(min_value=0.0, max_value=100.0, allow_nan=False)),
        risk=st.one_of(st.none(), st.sampled_from(["low", "medium", "high"])),
        filename=st.one_of(st.none(), st.text(min_size=1, max_size=50).filter(lambda s: s.strip())),
    )


def _build_mock(tid: str, score, risk, filename) -> MagicMock:
    obj = MagicMock()
    obj.task_id = tid
    obj.status = "completed"
    obj.created_at = datetime(2024, 3, 1, 10, 0, 0, tzinfo=timezone.utc)
    obj.result = {
        "filename": filename,
        "data": {
            "score": {"score": score, "risk_level": risk, "factors": [], "normalized_scores": {}},
            "metrics": {},
            "ratios": {},
        },
    } if score is not None or risk is not None or filename is not None else None
    return obj


@given(analyses=st.lists(_analysis_strategy(), min_size=0, max_size=50))
@settings(max_examples=100)
def test_analyses_list_response_structure(analyses):
    # Feature: analysis-history-visualization, Property 1: структура ответа GET /analyses
    # Validates: Requirements 1.2, 1.4
    total = len(analyses)

    app.dependency_overrides[get_api_key] = _auth_ok
    app.state.limiter.enabled = False
    try:
        with patch(
            "src.routers.analyses.get_analyses_list",
            new_callable=AsyncMock,
            return_value=(analyses, total),
        ):
            with TestClient(app) as client:
                response = client.get("/analyses?page=1&page_size=50")
    finally:
        app.dependency_overrides.pop(get_api_key, None)
        app.state.limiter.enabled = True

    assert response.status_code == 200
    body = response.json()

    # Top-level structure
    assert "items" in body
    assert "total" in body
    assert "page" in body
    assert "page_size" in body
    assert isinstance(body["items"], list)
    assert isinstance(body["total"], int)
    assert isinstance(body["page"], int)
    assert isinstance(body["page_size"], int)
    assert body["total"] == total

    # Per-item structure
    required_fields = {"task_id", "status", "created_at", "score", "risk_level", "filename"}
    for item in body["items"]:
        assert required_fields.issubset(item.keys()), f"Missing fields in item: {item.keys()}"
        assert isinstance(item["task_id"], str)
        assert isinstance(item["status"], str)
        assert isinstance(item["created_at"], str)
        assert item["score"] is None or isinstance(item["score"], (int, float))
        assert item["risk_level"] is None or isinstance(item["risk_level"], str)
        assert item["filename"] is None or isinstance(item["filename"], str)


# ---------------------------------------------------------------------------
# Property 2: Сортировка по created_at DESC
# Feature: analysis-history-visualization, Property 2: сортировка по created_at DESC
# Validates: Requirements 1.5
# ---------------------------------------------------------------------------

from hypothesis.strategies import composite


@composite
def _sorted_analyses_strategy(draw):
    """Generate a list of mock analyses pre-sorted by created_at DESC (as CRUD would return)."""
    n = draw(st.integers(min_value=2, max_value=20))
    # Generate n distinct timestamps and sort descending
    timestamps = draw(
        st.lists(
            st.datetimes(
                min_value=datetime(2020, 1, 1),
                max_value=datetime(2025, 12, 31),
                timezones=st.just(timezone.utc),
            ),
            min_size=n,
            max_size=n,
            unique=True,
        )
    )
    timestamps_desc = sorted(timestamps, reverse=True)

    analyses = []
    for ts in timestamps_desc:
        obj = MagicMock()
        obj.task_id = str(uuid.uuid4())
        obj.status = "completed"
        obj.created_at = ts
        obj.result = None
        analyses.append(obj)
    return analyses


@given(analyses=_sorted_analyses_strategy())
@settings(max_examples=100)
def test_analyses_sorted_by_created_at_desc(analyses):
    # Feature: analysis-history-visualization, Property 2: сортировка по created_at DESC
    # Validates: Requirements 1.5
    total = len(analyses)

    app.dependency_overrides[get_api_key] = _auth_ok
    app.state.limiter.enabled = False
    try:
        with patch(
            "src.routers.analyses.get_analyses_list",
            new_callable=AsyncMock,
            return_value=(analyses, total),
        ):
            with TestClient(app) as client:
                response = client.get(f"/analyses?page=1&page_size={total}")
    finally:
        app.dependency_overrides.pop(get_api_key, None)
        app.state.limiter.enabled = True

    assert response.status_code == 200
    items = response.json()["items"]
    assert len(items) == total

    # Verify descending order: each created_at >= next
    for i in range(len(items) - 1):
        assert items[i]["created_at"] >= items[i + 1]["created_at"], (
            f"Order violation at index {i}: "
            f"{items[i]['created_at']} < {items[i + 1]['created_at']}"
        )


# ---------------------------------------------------------------------------
# Property 4: Round-trip GET /analyses/{task_id}
# Feature: analysis-history-visualization, Property 4: round-trip GET /analyses/{task_id}
# Validates: Requirements 2.2
# ---------------------------------------------------------------------------

from hypothesis.strategies import composite as _composite

# Reusable strategies for result payloads
_status_strategy = st.sampled_from(["completed", "processing", "failed"])

_metrics_strategy = st.dictionaries(
    keys=st.text(min_size=1, max_size=20, alphabet=st.characters(whitelist_categories=("Ll", "Lu", "Nd"), whitelist_characters="_")),
    values=st.one_of(st.floats(min_value=-1e6, max_value=1e6, allow_nan=False, allow_infinity=False), st.integers(min_value=-1000000, max_value=1000000)),
    max_size=5,
)

_result_strategy = st.one_of(
    st.none(),
    st.fixed_dictionaries({
        "filename": st.one_of(st.none(), st.text(min_size=1, max_size=30)),
        "data": st.fixed_dictionaries({
            "text": st.text(max_size=50),
            "metrics": _metrics_strategy,
            "ratios": _metrics_strategy,
            "score": st.fixed_dictionaries({
                "score": st.floats(min_value=0.0, max_value=100.0, allow_nan=False),
                "risk_level": st.sampled_from(["low", "medium", "high", "critical"]),
                "factors": st.just([]),
                "normalized_scores": st.just({}),
            }),
            "nlp": st.just({"risks": [], "key_factors": [], "recommendations": []}),
        }),
    }),
)


@composite
def _analysis_detail_strategy(draw):
    obj = MagicMock()
    obj.task_id = draw(st.uuids().map(str))
    obj.status = draw(_status_strategy)
    obj.created_at = datetime(2024, 6, 1, 0, 0, 0, tzinfo=timezone.utc)
    obj.result = draw(_result_strategy)
    return obj


@given(analysis=_analysis_detail_strategy())
@settings(max_examples=100)
def test_get_analysis_detail_roundtrip(analysis):
    # Feature: analysis-history-visualization, Property 4: round-trip GET /analyses/{task_id}
    # Validates: Requirements 2.2
    from src.utils.masking import mask_analysis_data as _mask

    app.dependency_overrides[get_api_key] = _auth_ok
    app.state.limiter.enabled = False
    try:
        with patch(
            "src.routers.analyses.get_analysis",
            new_callable=AsyncMock,
            return_value=analysis,
        ):
            # Ensure DEMO_MODE is off for a clean round-trip check
            with patch.dict("os.environ", {"DEMO_MODE": "0"}, clear=False):
                with TestClient(app) as client:
                    response = client.get(f"/analyses/{analysis.task_id}")
    finally:
        app.dependency_overrides.pop(get_api_key, None)
        app.state.limiter.enabled = True

    assert response.status_code == 200
    body = response.json()

    # task_id and status must round-trip exactly
    assert body["task_id"] == analysis.task_id
    assert body["status"] == analysis.status

    # data must equal the inner analysis payload from DB result["data"]
    masked_result = _mask(analysis.result or {}, False) or None
    expected_data = (
        masked_result.get("data")
        if isinstance(masked_result, dict)
        else None
    )
    if expected_data == {}:
        expected_data = None
    assert body["data"] == expected_data
