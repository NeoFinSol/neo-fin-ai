"""
Unit tests for confidence score logic in pdf_extractor.

Tests cover:
1. Confidence mapping for each extraction source
2. Fallback for unknown sources
3. Confidence threshold filtering
4. Metadata preservation after filtering

Run: pytest tests/test_confidence_score.py -v
"""

import pytest

from src.analysis.pdf_extractor import (
    CONFIDENCE_THRESHOLD,
    ExtractionMetadata,
    ExtractionSource,
)
from src.analysis.pdf_extractor import (
    apply_confidence_filter as _apply_confidence_filter,
)
from src.analysis.pdf_extractor import determine_source

# =============================================================================
# Test 1: Confidence Mapping
# =============================================================================

class TestConfidenceMapping:
    """Test exact confidence values for each extraction source."""

    def test_table_exact_confidence_is_0_9(self):
        """table_exact source should have confidence 0.9"""
        source, confidence = determine_source("table", is_exact=True)
        assert source == "table_exact"
        assert confidence == 0.9

    def test_table_partial_confidence_is_0_7(self):
        """table_partial source should have confidence 0.7"""
        source, confidence = determine_source("table", is_exact=False)
        assert source == "table_partial"
        assert confidence == 0.7

    def test_text_regex_confidence_is_0_5(self):
        """text_regex source should have confidence 0.5"""
        source, confidence = determine_source("text_regex")
        assert source == "text_regex"
        assert confidence == 0.5

    def test_derived_confidence_is_0_3(self):
        """derived source should have confidence 0.3"""
        source, confidence = determine_source("", is_derived=True)
        assert source == "derived"
        assert confidence == 0.3


# =============================================================================
# Test 2: Fallback for Unknown Source
# =============================================================================

class TestUnknownSourceFallback:
    """Test fallback behavior for unknown extraction sources."""

    def test_unknown_source_falls_back_to_derived(self):
        """Unknown source should fallback to 'derived' with confidence 0.3"""
        source, confidence = determine_source("random_unknown_source")
        assert source == "derived"
        assert confidence == 0.3

    def test_empty_string_source_falls_back_to_derived(self):
        """Empty string source should fallback to 'derived'"""
        source, confidence = determine_source("")
        assert source == "derived"
        assert confidence == 0.3


# =============================================================================
# Test 3: Confidence Threshold Filtering
# =============================================================================

class TestConfidenceThresholdFiltering:
    """Test that values are filtered correctly based on CONFIDENCE_THRESHOLD."""

    def test_value_with_high_confidence_passes(self):
        """Value with confidence 0.9 should pass filter (threshold=0.5)"""
        # (value, confidence) above threshold
        filtered, metadata = _apply_confidence_filter({
            "revenue": ExtractionMetadata(value=1000.0, confidence=0.9, source="table_exact")
        })
        assert filtered["revenue"] == 1000.0

    def test_value_at_threshold_passes(self):
        """Value with confidence exactly at threshold (0.5) should pass"""
        filtered, metadata = _apply_confidence_filter({
            "revenue": ExtractionMetadata(value=1000.0, confidence=0.5, source="text_regex")
        })
        assert filtered["revenue"] == 1000.0

    def test_value_below_threshold_is_none(self):
        """Value with confidence 0.3 should be filtered to None (threshold=0.5)"""
        filtered, metadata = _apply_confidence_filter({
            "revenue": ExtractionMetadata(value=1000.0, confidence=0.3, source="derived")
        })
        assert filtered["revenue"] is None

    def test_value_with_confidence_0_7_passes(self):
        """Value with confidence 0.7 should pass filter"""
        filtered, metadata = _apply_confidence_filter({
            "revenue": ExtractionMetadata(value=1000.0, confidence=0.7, source="table_partial")
        })
        assert filtered["revenue"] == 1000.0


# =============================================================================
# Test 4: Dictionary Filtering
# =============================================================================

class TestDictionaryFiltering:
    """Test filtering of complete metrics dictionaries."""

    def test_mixed_confidence_values(self):
        """
        Test filtering with mixed confidence values.
        
        Input:
            revenue: (1000, 0.9) - should pass
            profit: (100, 0.3) - should be filtered to None
        
        Expected:
            revenue: 1000
            profit: None
        """
        metadata = {
            "revenue": ExtractionMetadata(value=1000.0, confidence=0.9, source="table_exact"),
            "profit": ExtractionMetadata(value=100.0, confidence=0.3, source="derived"),
        }
        
        filtered, extraction_metadata = _apply_confidence_filter(metadata)
        
        assert filtered["revenue"] == 1000.0
        assert filtered["profit"] is None

    def test_all_values_below_threshold(self):
        """All values below threshold should all become None"""
        metadata = {
            "revenue": ExtractionMetadata(value=1000.0, confidence=0.3, source="derived"),
            "profit": ExtractionMetadata(value=100.0, confidence=0.3, source="derived"),
        }
        
        filtered, extraction_metadata = _apply_confidence_filter(metadata)
        
        assert filtered["revenue"] is None
        assert filtered["profit"] is None

    def test_all_values_above_threshold(self):
        """All values above threshold should all pass"""
        metadata = {
            "revenue": ExtractionMetadata(value=1000.0, confidence=0.9, source="table_exact"),
            "profit": ExtractionMetadata(value=100.0, confidence=0.7, source="table_partial"),
        }
        
        filtered, extraction_metadata = _apply_confidence_filter(metadata)
        
        assert filtered["revenue"] == 1000.0
        assert filtered["profit"] == 100.0

    def test_none_value_always_preserved(self):
        """None values should remain None regardless of confidence"""
        metadata = {
            "revenue": ExtractionMetadata(value=None, confidence=0.9, source="table_exact"),
        }
        
        filtered, extraction_metadata = _apply_confidence_filter(metadata)
        
        assert filtered["revenue"] is None


# =============================================================================
# Test 5: Metadata Preservation
# =============================================================================

class TestMetadataPreservation:
    """Test that extraction metadata is preserved after filtering."""

    def test_metadata_preserved_for_filtered_values(self):
        """
        Metadata should be preserved even when value is filtered to None.
        
        Input:
            profit: (100, 0.3, "derived") - filtered to None
        
        Expected:
            metadata["profit"] = {"confidence": 0.3, "source": "derived"}
        """
        metadata = {
            "profit": ExtractionMetadata(value=100.0, confidence=0.3, source="derived"),
        }
        
        filtered, extraction_metadata = _apply_confidence_filter(metadata)
        
        # Value is filtered
        assert filtered["profit"] is None
        
        # But metadata is preserved
        assert extraction_metadata["profit"]["confidence"] == 0.3
        assert extraction_metadata["profit"]["source"] == "derived"

    def test_metadata_preserved_for_passed_values(self):
        """Metadata should be preserved for values that pass filter"""
        metadata = {
            "revenue": ExtractionMetadata(value=1000.0, confidence=0.9, source="table_exact"),
        }
        
        filtered, extraction_metadata = _apply_confidence_filter(metadata)
        
        # Value passes
        assert filtered["revenue"] == 1000.0
        
        # Metadata is preserved
        assert extraction_metadata["revenue"]["confidence"] == 0.9
        assert extraction_metadata["revenue"]["source"] == "table_exact"

    def test_all_keys_present_in_metadata(self):
        """All original keys should be present in metadata output"""
        metadata = {
            "revenue": ExtractionMetadata(value=1000.0, confidence=0.9, source="table_exact"),
            "profit": ExtractionMetadata(value=100.0, confidence=0.3, source="derived"),
            "assets": ExtractionMetadata(value=5000.0, confidence=0.5, source="text_regex"),
        }
        
        filtered, extraction_metadata = _apply_confidence_filter(metadata)
        
        # All keys present in both outputs
        assert set(filtered.keys()) == {"revenue", "profit", "assets"}
        assert set(extraction_metadata.keys()) == {"revenue", "profit", "assets"}


# =============================================================================
# Test 6: Custom Threshold
# =============================================================================

class TestCustomThreshold:
    """Test filtering with custom threshold values."""

    def test_custom_threshold_high(self):
        """With threshold=0.8, only 0.9 confidence should pass"""
        metadata = {
            "revenue": ExtractionMetadata(value=1000.0, confidence=0.9, source="table_exact"),
            "profit": ExtractionMetadata(value=100.0, confidence=0.7, source="table_partial"),
        }
        
        filtered, _ = _apply_confidence_filter(metadata, threshold=0.8)
        
        assert filtered["revenue"] == 1000.0
        assert filtered["profit"] is None

    def test_custom_threshold_low(self):
        """With threshold=0.2, all values should pass"""
        metadata = {
            "revenue": ExtractionMetadata(value=1000.0, confidence=0.3, source="derived"),
            "profit": ExtractionMetadata(value=100.0, confidence=0.3, source="derived"),
        }
        
        filtered, _ = _apply_confidence_filter(metadata, threshold=0.2)
        
        assert filtered["revenue"] == 1000.0
        assert filtered["profit"] == 100.0

    def test_threshold_boundary_exact(self):
        """Test exact boundary: confidence == threshold should pass"""
        metadata = {
            "revenue": ExtractionMetadata(value=1000.0, confidence=0.5, source="text_regex"),
        }
        
        # At threshold (0.5 == 0.5) → should pass
        filtered, _ = _apply_confidence_filter(metadata, threshold=0.5)
        assert filtered["revenue"] == 1000.0
        
        # Just below threshold (0.5 < 0.51) → should fail
        filtered, _ = _apply_confidence_filter(metadata, threshold=0.51)
        assert filtered["revenue"] is None
