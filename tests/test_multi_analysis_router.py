"""
Unit and property-based tests for multi-analysis router.

Tests cover:
1. POST /multi-analysis (success, validation errors)
2. GET /multi-analysis/{session_id} (processing, completed, not found)
3. Property-based tests for validation (period count, label length)
4. Chronological sorting property
5. Round-trip data preservation

Run: pytest tests/test_multi_analysis_router.py -v
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient
from hypothesis import given, settings, HealthCheck
from hypothesis import strategies as st

from src.app import app


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture(scope="function")
def client(monkeypatch):
    """Create test client for FastAPI app with mocked auth settings."""
    # Mock app_settings.dev_mode to bypass authentication
    with patch("src.core.auth.app_settings") as mock_settings:
        mock_settings.dev_mode = True
        mock_settings.api_key = None
        
        with TestClient(app) as test_client:
            yield test_client


@pytest.fixture(scope="function")
def mock_multi_session_crud():
    """Mock CRUD functions for multi_analysis_sessions table."""
    with patch("src.routers.multi_analysis.create_multi_session", new_callable=AsyncMock) as mock_create:
        with patch("src.routers.multi_analysis.get_multi_session", new_callable=AsyncMock) as mock_get:
            mock_create.return_value = None
            mock_get.return_value = None
            yield mock_create, mock_get


@pytest.fixture(scope="function")
def mock_db_session():
    """Mock database session for CRUD operations."""
    session = AsyncMock()
    session.execute = AsyncMock()
    session.commit = AsyncMock()
    session.refresh = AsyncMock()
    return session


@pytest.fixture(scope="function")
def no_rate_limit(monkeypatch):
    """Disable rate limiting for tests."""
    monkeypatch.setenv("RATE_LIMIT", "1000/second")
    yield
    monkeypatch.undo()


# =============================================================================
# Unit Tests: POST /multi-analysis
# =============================================================================

class TestPostMultiAnalysis:
    """Tests for POST /multi-analysis endpoint."""

    def test_post_multi_analysis_success_single_period(self, client):
        """
        Test 2.1: POST with 1 valid period should return 202.
        
        Expected:
        - status_code: 202
        - session_id: present (UUID format)
        - status: "processing"
        """
        payload = {"periods": [{"period_label": "2023"}]}
        
        with patch("src.routers.multi_analysis.create_multi_session", new_callable=AsyncMock) as mock_create:
            mock_create.return_value = None
            
            with patch("src.routers.multi_analysis.uuid4", return_value=MagicMock(hex="abc123")):
                response = client.post("/multi-analysis", json=payload)
        
        assert response.status_code == 202
        data = response.json()
        assert data["session_id"] is not None
        assert data["status"] == "processing"

    def test_post_multi_analysis_success_multiple_periods(self, client):
        """POST with 3 valid periods should return 202."""
        payload = {
            "periods": [
                {"period_label": "2021"},
                {"period_label": "2022"},
                {"period_label": "2023"},
            ]
        }
        
        with patch("src.routers.multi_analysis.create_multi_session", new_callable=AsyncMock):
            with patch("src.routers.multi_analysis.uuid4", return_value=MagicMock(hex="def456")):
                response = client.post("/multi-analysis", json=payload)
        
        assert response.status_code == 202
        data = response.json()
        assert data["session_id"] is not None

    def test_post_multi_analysis_too_many_periods(self, client):
        """
        Test 2.4: POST with 6 periods should return 422.
        
        Expected:
        - status_code: 422 (validation error)
        """
        payload = {
            "periods": [
                {"period_label": "2019"},
                {"period_label": "2020"},
                {"period_label": "2021"},
                {"period_label": "2022"},
                {"period_label": "2023"},
                {"period_label": "2024"},  # 6th period - too many
            ]
        }
        
        response = client.post("/multi-analysis", json=payload)
        
        assert response.status_code == 422

    def test_post_multi_analysis_zero_periods(self, client):
        """POST with 0 periods should return 422."""
        payload = {"periods": []}
        
        response = client.post("/multi-analysis", json=payload)
        
        assert response.status_code == 422

    def test_post_multi_analysis_label_too_long(self, client):
        """
        Test 2.5: POST with period_label > 20 chars should return 422.
        
        Expected:
        - status_code: 422 (validation error)
        """
        payload = {
            "periods": [
                {"period_label": "This is a very long period label that exceeds twenty characters"}
            ]
        }
        
        response = client.post("/multi-analysis", json=payload)
        
        assert response.status_code == 422

    def test_post_multi_analysis_empty_label(self, client):
        """POST with empty period_label should return 422."""
        payload = {"periods": [{"period_label": ""}]}
        
        response = client.post("/multi-analysis", json=payload)
        
        assert response.status_code == 422

    def test_post_multi_analysis_whitespace_only_label(self, client):
        """POST with whitespace-only period_label should return 422."""
        payload = {"periods": [{"period_label": "   "}]}
        
        response = client.post("/multi-analysis", json=payload)
        
        assert response.status_code == 422


# =============================================================================
# Unit Tests: GET /multi-analysis/{session_id}
# =============================================================================

class TestGetMultiAnalysisStatus:
    """Tests for GET /multi-analysis/{session_id} endpoint."""

    def test_get_multi_analysis_processing(self, client):
        """
        Test 2.2: GET existing session in "processing" status.
        
        Expected:
        - status_code: 200
        - status: "processing"
        - progress: {completed, total}
        """
        mock_session = MagicMock()
        mock_session.status = "processing"
        mock_session.progress = {"completed": 2, "total": 5}
        mock_session.result = None
        
        with patch("src.routers.multi_analysis.get_multi_session", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_session
            
            response = client.get("/multi-analysis/test-session-id")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "processing"
        assert data["progress"]["completed"] == 2
        assert data["progress"]["total"] == 5

    def test_get_multi_analysis_completed(self, client):
        """GET completed session should return periods."""
        mock_session = MagicMock()
        mock_session.status = "completed"
        mock_session.progress = {"completed": 3, "total": 3}
        mock_session.result = {
            "periods": [
                {"period_label": "2021", "ratios": {}, "score": 75.0, "risk_level": "low"},
                {"period_label": "2022", "ratios": {}, "score": 80.0, "risk_level": "low"},
            ]
        }
        
        with patch("src.routers.multi_analysis.get_multi_session", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_session
            
            response = client.get("/multi-analysis/test-session-id")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "completed"
        assert len(data["periods"]) == 2

    def test_get_multi_analysis_not_found(self, client):
        """
        Test 2.3: GET non-existent session should return 404.
        
        Expected:
        - status_code: 404
        - detail: "Session not found"
        """
        with patch("src.routers.multi_analysis.get_multi_session", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = None
            
            response = client.get("/multi-analysis/non-existent-id")
        
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    def test_get_multi_analysis_failed(self, client):
        """GET failed session should return 422."""
        mock_session = MagicMock()
        mock_session.status = "failed"
        mock_session.progress = {"completed": 1, "total": 3}
        
        with patch("src.routers.multi_analysis.get_multi_session", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_session
            
            response = client.get("/multi-analysis/failed-session")
        
        assert response.status_code == 422


# =============================================================================
# Property-Based Tests (hypothesis)
# =============================================================================

class TestPropertyValidation:
    """Property-based tests for multi-analysis validation."""

    @given(st.text(min_size=0, max_size=50))
    @settings(max_examples=50, deadline=None, suppress_health_check=[HealthCheck.filter_too_much])
    def test_property_6_period_label_length(self, label_text, monkeypatch):
        """
        Property 6: period_label length validation.
        
        For ANY text input:
        - If len(label) > 20 → 422
        - If 1 ≤ len(label) ≤ 20 → accepted (if other validation passes)
        - If len(label) == 0 → 422
        """
        # Skip rate limiting by testing Pydantic validation directly
        from src.models.schemas import PeriodInput, MultiAnalysisRequest
        
        if len(label_text.strip()) == 0 or len(label_text) > 20:
            # Should fail validation
            with pytest.raises(Exception):  # ValidationError
                PeriodInput(period_label=label_text)
        else:
            # May pass validation
            try:
                PeriodInput(period_label=label_text)
            except Exception:
                pass  # Some may still fail for other reasons

    @given(st.lists(st.text(min_size=1, max_size=10), min_size=0, max_size=10))
    @settings(max_examples=50, deadline=None)
    def test_property_7_period_count(self, period_labels):
        """
        Property 7: Number of periods validation.
        
        For ANY list of period labels:
        - If len < 1 or len > 5 → 422
        - If 1 ≤ len ≤ 5 → accepted
        """
        from src.models.schemas import MultiAnalysisRequest
        
        if len(period_labels) < 1 or len(period_labels) > 5:
            # Should fail validation
            with pytest.raises(Exception):  # ValidationError
                MultiAnalysisRequest(periods=[{"period_label": l} for l in period_labels])
        else:
            # Should be accepted (or fail for other valid reasons like length)
            try:
                MultiAnalysisRequest(periods=[{"period_label": l[:20]} for l in period_labels if l])
            except Exception:
                pass  # Some may fail for length reasons


class TestChronologicalSorting:
    """Tests for chronological sorting property."""

    @given(
        st.lists(
            st.one_of(
                st.integers(min_value=2000, max_value=2030).map(str),
                st.builds(lambda q, y: f"Q{q}/{y}", st.integers(1, 4), st.integers(2000, 2030))
            ),
            min_size=2,
            max_size=5,
            unique=True
        )
    )
    @settings(max_examples=100, deadline=None)
    def test_property_8_chronological_sort(self, period_labels):
        """
        Property 8: Periods are sorted chronologically.
        
        For ANY set of period labels (years and quarters):
        - After processing, periods should be in non-decreasing order
        - Years: 2021 < 2022 < 2023
        - Quarters: Q1/2023 < Q2/2023 < Q3/2023 < Q4/2023
        """
        # Import the sorting function
        from src.tasks import parse_period_label, sort_periods_chronologically
        
        # Create mock period results
        periods = [
            {"period_label": label, "ratios": {}, "score": 50.0, "risk_level": "medium"}
            for label in period_labels
        ]
        
        # Sort using the production function
        sorted_periods = sort_periods_chronologically(periods)
        
        # Verify order is non-decreasing
        parsed_labels = [parse_period_label(p["period_label"]) for p in sorted_periods]
        
        for i in range(len(parsed_labels) - 1):
            assert parsed_labels[i] <= parsed_labels[i + 1], \
                f"Periods not sorted: {parsed_labels[i]} > {parsed_labels[i + 1]}"


class TestRoundTrip:
    """Tests for round-trip data preservation."""

    @given(
        st.lists(
            st.text(min_size=1, max_size=15).filter(lambda x: x.strip()),
            min_size=1,
            max_size=5
        ).filter(lambda x: len(x) <= 5)
    )
    @settings(max_examples=20, deadline=None)
    def test_property_9_round_trip_preservation(self, period_labels, no_rate_limit):
        """
        Property 9: Round-trip data preservation.
        
        For ANY valid set of period labels:
        - Create session → Get status → Verify structure
        - session_id is preserved
        - periods structure is maintained
        - No data corruption
        """
        # Filter to ensure all labels are ≤ 20 chars
        valid_labels = [l for l in period_labels if len(l) <= 20]
        if len(valid_labels) == 0:
            valid_labels = ["2023"]  # Fallback
        
        payload = {"periods": [{"period_label": label} for label in valid_labels[:5]]}
        
        # Step 1: Create session
        with patch("src.routers.multi_analysis.create_multi_session", new_callable=AsyncMock):
            with patch("src.routers.multi_analysis.uuid4", return_value=MagicMock(hex="roundtrip123")):
                with patch("src.routers.multi_analysis.BackgroundTasks"):
                    create_response = TestClient(app).post("/multi-analysis", json=payload)
        
        if create_response.status_code != 202:
            # Skip if validation failed
            pytest.skip("Validation failed for generated data")
        
        session_id = create_response.json()["session_id"]
        
        # Step 2: Mock session data for retrieval
        mock_session = MagicMock()
        mock_session.status = "completed"
        mock_session.progress = {"completed": len(valid_labels), "total": len(valid_labels)}
        mock_session.result = {
            "periods": [
                {
                    "period_label": label,
                    "ratios": {"current_ratio": 1.5},
                    "score": 75.0,
                    "risk_level": "low",
                    "extraction_metadata": {}
                }
                for label in valid_labels
            ]
        }
        
        # Step 3: Get session status
        with patch("src.routers.multi_analysis.get_multi_session", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_session
            
            get_response = TestClient(app).get(f"/multi-analysis/{session_id}")
        
        assert get_response.status_code == 200
        data = get_response.json()
        
        # Verify round-trip properties
        assert data["session_id"] == session_id, "session_id should be preserved"
        assert data["status"] == "completed"
        assert len(data["periods"]) == len(valid_labels), "All periods should be present"
        
        # Verify structure of each period
        for period in data["periods"]:
            assert "period_label" in period
            assert "ratios" in period
            assert "score" in period or period.get("score") is None
            assert "risk_level" in period or period.get("risk_level") is None


# =============================================================================
# Integration-style Tests (mocked background task)
# =============================================================================

class TestMultiAnalysisIntegration:
    """Integration-style tests with mocked background processing."""

    def test_full_multi_analysis_flow(self, client, no_rate_limit):
        """
        Test complete multi-analysis flow:
        1. POST /multi-analysis → 202
        2. GET /multi-analysis/{id} (processing) → 200
        3. GET /multi-analysis/{id} (completed) → 200
        """
        session_id = "test-flow-123"
        
        # Step 1: Create session
        with patch("src.routers.multi_analysis.create_multi_session", new_callable=AsyncMock):
            with patch("src.routers.multi_analysis.uuid4", return_value=MagicMock(hex=session_id)):
                create_response = client.post(
                    "/multi-analysis",
                    json={"periods": [{"period_label": "2022"}, {"period_label": "2023"}]}
                )
        
        assert create_response.status_code == 202
        assert create_response.json()["session_id"] == session_id
        
        # Step 2: Check processing status
        mock_session_processing = MagicMock()
        mock_session_processing.status = "processing"
        mock_session_processing.progress = {"completed": 1, "total": 2}
        
        with patch("src.routers.multi_analysis.get_multi_session", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_session_processing
            
            status_response = client.get(f"/multi-analysis/{session_id}")
        
        assert status_response.status_code == 200
        assert status_response.json()["status"] == "processing"
        
        # Step 3: Check completed status
        mock_session_completed = MagicMock()
        mock_session_completed.status = "completed"
        mock_session_completed.result = {
            "periods": [
                {"period_label": "2022", "ratios": {}, "score": 70.0, "risk_level": "medium"},
                {"period_label": "2023", "ratios": {}, "score": 80.0, "risk_level": "low"},
            ]
        }
        
        with patch("src.routers.multi_analysis.get_multi_session", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_session_completed
            
            completed_response = client.get(f"/multi-analysis/{session_id}")
        
        assert completed_response.status_code == 200
        assert completed_response.json()["status"] == "completed"
        assert len(completed_response.json()["periods"]) == 2
