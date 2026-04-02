"""Additional tests for helper branches around tasks/scoring/file cleanup."""

import io
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.exc import SQLAlchemyError

from src.analysis.scoring import build_score_payload, translate_risk_level
from src.db.crud import AnalysisAlreadyExistsError
from src.tasks import _ensure_analysis_exists, _run_ai_analysis_phase
from src.utils.file_utils import cleanup_temp_file


class TestCleanupTempFile:
    """Tests for cleanup_temp_file — covers all branches."""

    def test_none_is_noop(self):
        cleanup_temp_file(None)

    def test_file_like_object_is_closed(self):
        mock_file = MagicMock()
        mock_file.close = MagicMock()
        cleanup_temp_file(mock_file)
        mock_file.close.assert_called_once()

    def test_bytesio_is_closed(self):
        buf = io.BytesIO(b"data")
        cleanup_temp_file(buf)
        assert buf.closed

    def test_string_path_deleted(self, tmp_path):
        file_path = tmp_path / "test.pdf"
        file_path.write_bytes(b"data")
        cleanup_temp_file(str(file_path))
        assert not file_path.exists()

    def test_path_object_deleted(self, tmp_path):
        file_path = tmp_path / "test.pdf"
        file_path.write_bytes(b"data")
        cleanup_temp_file(file_path)
        assert not file_path.exists()

    def test_nonexistent_path_no_error(self, tmp_path):
        cleanup_temp_file(str(tmp_path / "missing.pdf"))

    def test_close_exception_is_swallowed(self):
        mock_file = MagicMock()
        mock_file.close = MagicMock(side_effect=OSError("close failed"))
        cleanup_temp_file(mock_file)

    def test_invalid_path_type_no_error(self):
        cleanup_temp_file(12345)


class TestEnsureAnalysisExists:
    """Tests for _ensure_analysis_exists — covers happy path and DB fallback branches."""

    @pytest.mark.asyncio
    async def test_returns_true_when_existing_record_found(self):
        with patch("src.tasks.get_analysis", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = MagicMock()
            assert await _ensure_analysis_exists("task-1") is True

    @pytest.mark.asyncio
    async def test_creates_when_record_missing(self):
        with patch("src.tasks.get_analysis", new_callable=AsyncMock) as mock_get, \
             patch("src.tasks.create_analysis", new_callable=AsyncMock) as mock_create:
            mock_get.return_value = None
            mock_create.return_value = MagicMock()

            assert await _ensure_analysis_exists("task-2") is True
            mock_create.assert_awaited_once_with("task-2", "processing", None)

    @pytest.mark.asyncio
    async def test_handles_race_condition(self):
        with patch("src.tasks.get_analysis", new_callable=AsyncMock) as mock_get, \
             patch("src.tasks.create_analysis", new_callable=AsyncMock) as mock_create, \
             patch("src.tasks.update_analysis", new_callable=AsyncMock) as mock_update:
            mock_get.return_value = None
            mock_create.side_effect = AnalysisAlreadyExistsError("exists")
            mock_update.return_value = MagicMock()

            assert await _ensure_analysis_exists("task-3") is True
            mock_update.assert_awaited_once_with("task-3", "processing", None)

    @pytest.mark.asyncio
    async def test_returns_false_when_initial_read_fails(self):
        with patch("src.tasks.get_analysis", new_callable=AsyncMock) as mock_get:
            mock_get.side_effect = SQLAlchemyError("db down")
            assert await _ensure_analysis_exists("task-4") is False

    @pytest.mark.asyncio
    async def test_returns_false_when_create_fails(self):
        with patch("src.tasks.get_analysis", new_callable=AsyncMock) as mock_get, \
             patch("src.tasks.create_analysis", new_callable=AsyncMock) as mock_create:
            mock_get.return_value = None
            mock_create.side_effect = SQLAlchemyError("db down")
            assert await _ensure_analysis_exists("task-5") is False

    @pytest.mark.asyncio
    async def test_returns_false_when_race_recheck_fails(self):
        with patch("src.tasks.get_analysis", new_callable=AsyncMock) as mock_get, \
             patch("src.tasks.create_analysis", new_callable=AsyncMock) as mock_create, \
             patch("src.tasks.update_analysis", new_callable=AsyncMock) as mock_update:
            mock_get.return_value = None
            mock_create.side_effect = AnalysisAlreadyExistsError("exists")
            mock_update.return_value = None
            assert await _ensure_analysis_exists("task-6") is False


class TestBuildScorePayloadEdgeCases:
    """Tests for build_score_payload — covers missing branches and formatting guardrails."""

    def test_none_norm_val_gives_neutral_impact(self):
        raw_score = {
            "score": 50,
            "risk_level": "средний",
            "details": {"Коэффициент текущей ликвидности": None},
        }
        result = build_score_payload(raw_score, {"current_ratio": 1.5})
        factor = next(f for f in result["factors"] if f["name"] == "Текущая ликвидность")
        assert factor["impact"] == "neutral"

    def test_non_numeric_ratio_value_formatted_without_crash(self):
        raw_score = {
            "score": 60,
            "risk_level": "средний",
            "details": {"Коэффициент текущей ликвидности": 0.8},
        }
        result = build_score_payload(raw_score, {"current_ratio": "not-a-number"})
        assert result["factors"][0]["description"] == "Значение: not-a-number"

    def test_none_ratio_value_shows_unavailable(self):
        raw_score = {
            "score": 60,
            "risk_level": "средний",
            "details": {"Коэффициент текущей ликвидности": 0.8},
        }
        result = build_score_payload(raw_score, {"current_ratio": None})
        assert result["factors"][0]["description"] == "Данные недоступны"

    def test_unknown_ru_key_skipped(self):
        raw_score = {
            "score": 50,
            "risk_level": "средний",
            "details": {"Неизвестный коэффициент": 0.5},
        }
        result = build_score_payload(raw_score, {})
        assert result["factors"] == []

    def test_all_normalized_scores_initialized_to_none(self):
        raw_score = {"score": 0, "risk_level": "высокий", "details": {}}
        result = build_score_payload(raw_score, {})
        assert len(result["normalized_scores"]) == 15
        assert all(value is None for value in result["normalized_scores"].values())


class TestTranslateRiskLevel:
    def test_low(self):
        assert translate_risk_level("низкий") == "low"

    def test_medium(self):
        assert translate_risk_level("средний") == "medium"

    def test_high(self):
        assert translate_risk_level("высокий") == "high"

    def test_critical(self):
        assert translate_risk_level("критический") == "critical"

    def test_unknown_defaults_to_high(self):
        assert translate_risk_level("unknown") == "high"


class TestRunAiAnalysisPhase:
    """Tests for AI-analysis runtime status handling."""

    @pytest.mark.asyncio
    async def test_short_text_skips_narrative_and_keeps_recommendations(self):
        with patch("src.tasks.generate_recommendations", new_callable=AsyncMock) as mock_recommendations:
            mock_recommendations.return_value = [{"title": "stub"}]
            nlp_result, ai_runtime = await _run_ai_analysis_phase(
                text="too short",
                extracted_metrics={},
                ratios={},
                task_logger=MagicMock(),
                ai_provider="ollama",
            )

        assert ai_runtime["status"] == "skipped"
        assert ai_runtime["reason_code"] == "insufficient_text"
        assert nlp_result["recommendations"] == [{"title": "stub"}]

    @pytest.mark.asyncio
    async def test_narrative_failure_marks_provider_error(self):
        with patch("src.tasks.analyze_narrative_with_runtime", new_callable=AsyncMock) as mock_narrative, \
             patch("src.tasks.generate_recommendations", new_callable=AsyncMock) as mock_recommendations:
            mock_narrative.side_effect = RuntimeError("provider boom")
            mock_recommendations.return_value = []

            _, ai_runtime = await _run_ai_analysis_phase(
                text="x" * 800,
                extracted_metrics={},
                ratios={},
                task_logger=MagicMock(),
                ai_provider="ollama",
            )

        assert ai_runtime["status"] == "failed"
        assert ai_runtime["reason_code"] == "provider_error"

    @pytest.mark.asyncio
    async def test_narrative_success_propagates_runtime(self):
        with patch("src.tasks.analyze_narrative_with_runtime", new_callable=AsyncMock) as mock_narrative, \
             patch("src.tasks.generate_recommendations", new_callable=AsyncMock) as mock_recommendations:
            mock_narrative.return_value = (
                {"risks": ["r1"], "key_factors": ["k1"], "recommendations": []},
                {
                    "requested_provider": "ollama",
                    "effective_provider": "ollama",
                    "status": "succeeded",
                    "reason_code": None,
                },
            )
            mock_recommendations.return_value = [{"title": "rec"}]

            nlp_result, ai_runtime = await _run_ai_analysis_phase(
                text="x" * 800,
                extracted_metrics={},
                ratios={},
                task_logger=MagicMock(),
                ai_provider="ollama",
            )

        assert ai_runtime["status"] == "succeeded"
        assert ai_runtime["effective_provider"] == "ollama"
        assert nlp_result["recommendations"] == [{"title": "rec"}]
