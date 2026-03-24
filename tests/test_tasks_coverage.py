"""Additional tests for tasks.py — covers missing branches."""
import asyncio
import io
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from pathlib import Path

from src.tasks import (
    _cleanup_temp_file,
    _ensure_analysis_exists,
    _build_score_payload,
    _translate_risk_level,
    process_pdf,
)


class TestCleanupTempFile:
    """Tests for _cleanup_temp_file — covers all branches."""

    def test_none_is_noop(self):
        _cleanup_temp_file(None)  # should not raise

    def test_file_like_object_is_closed(self):
        mock_file = MagicMock()
        mock_file.close = MagicMock()
        _cleanup_temp_file(mock_file)
        mock_file.close.assert_called_once()

    def test_bytesio_is_closed(self):
        buf = io.BytesIO(b"data")
        _cleanup_temp_file(buf)
        assert buf.closed

    def test_string_path_deleted(self, tmp_path):
        f = tmp_path / "test.pdf"
        f.write_bytes(b"data")
        _cleanup_temp_file(str(f))
        assert not f.exists()

    def test_path_object_deleted(self, tmp_path):
        f = tmp_path / "test.pdf"
        f.write_bytes(b"data")
        _cleanup_temp_file(f)
        assert not f.exists()

    def test_nonexistent_path_no_error(self, tmp_path):
        _cleanup_temp_file(str(tmp_path / "nonexistent.pdf"))  # should not raise

    def test_close_exception_is_swallowed(self):
        mock_file = MagicMock()
        mock_file.close = MagicMock(side_effect=OSError("close failed"))
        _cleanup_temp_file(mock_file)  # should not raise

    def test_invalid_path_type_no_error(self):
        _cleanup_temp_file(12345)  # should not raise


class TestEnsureAnalysisExists:
    """Tests for _ensure_analysis_exists — covers DB unavailable path."""

    @pytest.mark.asyncio
    async def test_returns_true_when_update_succeeds(self):
        with patch("src.tasks.update_analysis", new_callable=AsyncMock) as mock_update:
            mock_update.return_value = MagicMock()  # non-None = exists
            result = await _ensure_analysis_exists("task-1")
            assert result is True

    @pytest.mark.asyncio
    async def test_creates_when_update_returns_none(self):
        with patch("src.tasks.update_analysis", new_callable=AsyncMock) as mock_update, \
             patch("src.tasks.create_analysis", new_callable=AsyncMock) as mock_create:
            mock_update.return_value = None
            mock_create.return_value = MagicMock()
            result = await _ensure_analysis_exists("task-2")
            assert result is True

    @pytest.mark.asyncio
    async def test_handles_race_condition(self):
        from src.db.crud import AnalysisAlreadyExistsError
        with patch("src.tasks.update_analysis", new_callable=AsyncMock) as mock_update, \
             patch("src.tasks.create_analysis", new_callable=AsyncMock) as mock_create:
            mock_update.side_effect = [None, MagicMock()]  # first None, then found
            mock_create.side_effect = AnalysisAlreadyExistsError("exists")
            result = await _ensure_analysis_exists("task-3")
            assert result is True

    @pytest.mark.asyncio
    async def test_returns_false_when_db_unavailable(self):
        from src.db.crud import AnalysisAlreadyExistsError
        with patch("src.tasks.update_analysis", new_callable=AsyncMock) as mock_update, \
             patch("src.tasks.create_analysis", new_callable=AsyncMock) as mock_create:
            mock_update.return_value = None  # first call: not found
            mock_create.side_effect = AnalysisAlreadyExistsError("exists")
            # Second update_analysis call returns None (DB unavailable)
            mock_update.side_effect = [None, None]
            result = await _ensure_analysis_exists("task-4")
            assert result is False


class TestBuildScorePayloadEdgeCases:
    """Tests for _build_score_payload — covers missing branches."""

    def test_none_norm_val_gives_neutral_impact(self):
        raw_score = {
            "score": 50,
            "risk_level": "средний",
            "details": {"Коэффициент текущей ликвидности": None},
        }
        ratios_en = {"current_ratio": 1.5}
        result = _build_score_payload(raw_score, ratios_en)
        factor = next(f for f in result["factors"] if f["name"] == "Текущая ликвидность")
        assert factor["impact"] == "neutral"

    def test_non_numeric_ratio_value_formatted(self):
        raw_score = {
            "score": 60,
            "risk_level": "средний",
            "details": {"Коэффициент текущей ликвидности": 0.8},
        }
        ratios_en = {"current_ratio": "not-a-number"}
        result = _build_score_payload(raw_score, ratios_en)
        # Should not crash
        assert len(result["factors"]) == 1

    def test_none_ratio_value_shows_dash(self):
        raw_score = {
            "score": 60,
            "risk_level": "средний",
            "details": {"Коэффициент текущей ликвидности": 0.8},
        }
        ratios_en = {"current_ratio": None}
        result = _build_score_payload(raw_score, ratios_en)
        factor = result["factors"][0]
        assert "—" in factor["description"]

    def test_unknown_ru_key_skipped(self):
        raw_score = {
            "score": 50,
            "risk_level": "средний",
            "details": {"Неизвестный коэффициент": 0.5},
        }
        ratios_en = {}
        result = _build_score_payload(raw_score, ratios_en)
        assert result["factors"] == []

    def test_all_normalized_scores_initialized_to_none(self):
        raw_score = {"score": 0, "risk_level": "высокий", "details": {}}
        result = _build_score_payload(raw_score, {})
        # All 13 keys should be present and None
        assert len(result["normalized_scores"]) == 13
        for v in result["normalized_scores"].values():
            assert v is None


class TestTranslateRiskLevel:
    def test_low(self):
        assert _translate_risk_level("низкий") == "low"

    def test_medium(self):
        assert _translate_risk_level("средний") == "medium"

    def test_high(self):
        assert _translate_risk_level("высокий") == "high"

    def test_unknown_defaults_to_high(self):
        assert _translate_risk_level("unknown") == "high"


class TestProcessPdfNlpAndRecommendations:
    """Tests for process_pdf — covers NLP/recommendations branches."""

    @pytest.mark.asyncio
    async def test_nlp_import_error_graceful(self):
        """ImportError in NLP analysis is handled gracefully."""
        with patch("src.tasks.update_analysis", new_callable=AsyncMock) as mock_update, \
             patch("src.tasks.create_analysis", new_callable=AsyncMock), \
             patch("src.tasks.pdf_extractor") as mock_extractor, \
             patch("src.tasks.calculate_ratios", return_value={}), \
             patch("src.tasks.calculate_integral_score", return_value={"score": 50, "risk_level": "средний", "details": {}}), \
             patch("src.tasks._extract_text_from_pdf", return_value="x" * 600), \
             patch("src.tasks._cleanup_temp_file"):

            mock_update.return_value = MagicMock()
            mock_extractor.is_scanned_pdf.return_value = False
            mock_extractor.extract_tables.return_value = []
            mock_extractor.parse_financial_statements.return_value = {}

            # Patch asyncio.wait_for to raise ImportError for NLP call
            original_wait_for = asyncio.wait_for
            call_count = [0]

            async def fake_wait_for(coro, timeout):
                call_count[0] += 1
                if call_count[0] == 1:
                    # First call is NLP — simulate ImportError
                    coro.close()
                    raise ImportError("no module named nlp_analysis")
                return await original_wait_for(coro, timeout)

            with patch("src.tasks.asyncio.wait_for", side_effect=fake_wait_for):
                await process_pdf("task-nlp", "/fake/path.pdf")

            mock_update.assert_called()

    @pytest.mark.asyncio
    async def test_nlp_timeout_graceful(self):
        """asyncio.TimeoutError in NLP is handled gracefully."""
        import asyncio as _asyncio

        with patch("src.tasks.update_analysis", new_callable=AsyncMock) as mock_update, \
             patch("src.tasks.create_analysis", new_callable=AsyncMock), \
             patch("src.tasks.pdf_extractor") as mock_extractor, \
             patch("src.tasks.calculate_ratios", return_value={}), \
             patch("src.tasks.calculate_integral_score", return_value={"score": 50, "risk_level": "средний", "details": {}}), \
             patch("src.tasks._extract_text_from_pdf", return_value="x" * 600), \
             patch("src.tasks._cleanup_temp_file"):

            mock_update.return_value = MagicMock()
            mock_extractor.is_scanned_pdf.return_value = False
            mock_extractor.extract_tables.return_value = []
            mock_extractor.parse_financial_statements.return_value = {}

            async def fake_analyze_narrative(text):
                raise _asyncio.TimeoutError()

            with patch("src.analysis.nlp_analysis.analyze_narrative", fake_analyze_narrative):
                await process_pdf("task-timeout", "/fake/path.pdf")

            mock_update.assert_called()

    @pytest.mark.asyncio
    async def test_db_unavailable_aborts(self):
        """If DB unavailable, process_pdf returns early."""
        with patch("src.tasks.update_analysis", new_callable=AsyncMock) as mock_update, \
             patch("src.tasks.create_analysis", new_callable=AsyncMock) as mock_create, \
             patch("src.tasks._cleanup_temp_file"):
            mock_update.return_value = None
            from sqlalchemy.exc import SQLAlchemyError
            mock_create.side_effect = SQLAlchemyError("db down")
            await process_pdf("task-db-fail", "/fake/path.pdf")
            # Should not crash, just return early
