"""
Property-based tests for confidence score system using hypothesis.

These tests verify that the confidence system behaves correctly
for ALL valid inputs, not just specific examples.

Properties tested:
1. Confidence scores are always in [0.0, 1.0]
2. Source → confidence mapping is correct and deterministic
3. Filter respects threshold boundary exactly
4. Reliable count matches filtered results
5. Metadata structure is always valid
6. System handles edge cases gracefully
7. Valid PDF metrics don't cause crashes

Run: pytest tests/test_confidence_properties.py -v
"""

import pytest
from hypothesis import HealthCheck, assume, given, settings
from hypothesis import strategies as st

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
# Hypothesis Strategies
# =============================================================================

# Valid extraction sources (legacy + mixed mode inputs)
VALID_SOURCES = st.sampled_from(
    ["table_exact", "table_partial", "text_regex", "derived", "issuer_fallback"]
)

# Valid extraction parameter combinations
MATCH_TYPE_STRATEGIES = st.one_of(
    st.just(("table", True, False)),  # table_exact
    st.just(("table", False, False)),  # table_partial
    st.just(("text_regex", False, False)),  # text_regex
    st.just(("", False, True)),  # derived
)

# Valid confidence values [0.0, 1.0]
CONFIDENCE_FLOAT = st.floats(min_value=0.0, max_value=1.0)

# Valid threshold values [0.0, 1.0]
THRESHOLD_FLOAT = st.floats(min_value=0.0, max_value=1.0)

# Metric names (simplified)
METRIC_NAME = st.text(min_size=1, max_size=50).filter(lambda x: x.strip() != "")

# Valid metric values (including None)
METRIC_VALUE = st.one_of(st.floats(min_value=-1e12, max_value=1e12), st.none())


# =============================================================================
# Property 1: Confidence Score in Valid Range
# =============================================================================


@given(MATCH_TYPE_STRATEGIES)
@settings(max_examples=100, deadline=None)
def test_confidence_score_in_range(match_params):
    """
    Property 1: For ANY extraction parameters, confidence is always in [0.0, 1.0].

    This ensures the confidence scoring system never produces invalid values.
    """
    match_type, is_exact, is_derived = match_params
    _, confidence = determine_source(
        match_type, is_exact=is_exact, is_derived=is_derived
    )

    # Confidence must be in valid range
    assert 0.0 <= confidence <= 1.0, f"Confidence {confidence} is out of range"


# =============================================================================
# Property 2: Correct Source → Confidence Mapping
# =============================================================================


@given(MATCH_TYPE_STRATEGIES)
@settings(max_examples=100, deadline=None)
def test_source_confidence_mapping(match_params):
    """
    Property 2: For ANY extraction parameters, the confidence mapping is exact.

    This ensures the mapping is consistent and matches the specification.
    """
    match_type, is_exact, is_derived = match_params
    returned_source, confidence = determine_source(
        match_type, is_exact=is_exact, is_derived=is_derived
    )

    # Determine expected source from params
    if is_derived:
        expected_source = "derived"
        expected_confidence = 0.35
    elif match_type == "table":
        expected_source = "table"
        expected_confidence = 0.92 if is_exact else 0.60
    elif match_type == "text_regex":
        expected_source = "text"
        expected_confidence = 0.56
    else:
        expected_source = "derived"
        expected_confidence = 0.35

    # Source should be returned correctly
    assert (
        returned_source == expected_source
    ), f"Expected {expected_source}, got {returned_source}"

    # Confidence should match expected value exactly
    assert (
        confidence == expected_confidence
    ), f"Expected {expected_confidence} for {returned_source}, got {confidence}"


# =============================================================================
# Property 3: Filter Respects Threshold Boundary
# =============================================================================


@given(
    st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False),
    st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False),
)
@settings(
    max_examples=200, deadline=None, suppress_health_check=[HealthCheck.filter_too_much]
)
def test_filter_respects_threshold_boundary(confidence, threshold):
    """
    Property 3: For ANY confidence and threshold values:
    - If confidence >= threshold → value passes
    - If confidence < threshold → value is filtered to None

    This is the core correctness property of the filtering system.
    """
    # Skip NaN/Infinity edge cases
    assume(confidence == confidence)  # NaN check
    assume(threshold == threshold)

    metadata = {
        "test_metric": ExtractionMetadata(
            value=100.0, confidence=confidence, source="table_exact"
        )
    }

    filtered, _ = _apply_confidence_filter(metadata, threshold=threshold)

    if confidence >= threshold:
        # Value should pass filter
        assert (
            filtered["test_metric"] == 100.0
        ), f"Value with confidence {confidence} should pass threshold {threshold}"
    else:
        # Value should be filtered to None
        assert (
            filtered["test_metric"] is None
        ), f"Value with confidence {confidence} should be filtered by threshold {threshold}"


# =============================================================================
# Property 4: Reliable Count Matches Filtered Results
# =============================================================================


@given(
    st.dictionaries(
        keys=METRIC_NAME,
        values=st.tuples(CONFIDENCE_FLOAT, st.floats(min_value=-1e10, max_value=1e10)),
        min_size=1,
        max_size=20,
    ),
    THRESHOLD_FLOAT,
)
@settings(
    max_examples=100, deadline=None, suppress_health_check=[HealthCheck.filter_too_much]
)
def test_reliable_count_matches_filter(metric_data, threshold):
    """
    Property 4: For ANY set of metrics and threshold:
    Count of non-None filtered values == count of confidence >= threshold

    This ensures the filtering is internally consistent.
    """
    # Build metadata dict
    metadata = {
        name: ExtractionMetadata(value=value, confidence=conf, source="table_exact")
        for name, (conf, value) in metric_data.items()
    }

    filtered, _ = _apply_confidence_filter(metadata, threshold=threshold)

    # Count non-None values in filtered result
    passed_count = sum(1 for v in filtered.values() if v is not None)

    # Count metrics with confidence >= threshold
    expected_count = sum(1 for m in metadata.values() if m.confidence >= threshold)

    assert (
        passed_count == expected_count
    ), f"Passed count {passed_count} != expected {expected_count}"


# =============================================================================
# Property 5: Metadata Structure Always Valid
# =============================================================================


@given(
    st.dictionaries(
        keys=METRIC_NAME,
        values=st.tuples(CONFIDENCE_FLOAT, METRIC_VALUE, VALID_SOURCES),
        min_size=1,
        max_size=15,
    )
)
@settings(max_examples=100, deadline=None)
def test_metadata_structure_always_valid(metric_data):
    """
    Property 5: For ANY input metadata, the output structure is always valid.

    Output must:
    - Have same keys as input
    - Each metadata entry has 'confidence' (float) and 'source' (str)
    """
    metadata = {
        name: ExtractionMetadata(value=value, confidence=conf, source=source)
        for name, (conf, value, source) in metric_data.items()
    }

    filtered, extraction_metadata = _apply_confidence_filter(metadata)

    # Keys must match
    assert set(filtered.keys()) == set(metadata.keys())
    assert set(extraction_metadata.keys()) == set(metadata.keys())

    # Each metadata entry must have valid structure
    for key, meta in extraction_metadata.items():
        assert "confidence" in meta, f"Missing 'confidence' for {key}"
        assert "source" in meta, f"Missing 'source' for {key}"
        assert isinstance(meta["confidence"], float), f"Confidence not float for {key}"
        assert 0.0 <= meta["confidence"] <= 1.0, f"Confidence out of range for {key}"
        assert meta["source"] in ["table", "text", "derived", "issuer_fallback"]
        assert "evidence_version" in meta
        assert "match_semantics" in meta
        assert "inference_mode" in meta


# =============================================================================
# Property 6: Edge Cases Handled Gracefully
# =============================================================================


@given(st.just(0.0) | st.just(1.0) | st.just(0.5))
@settings(max_examples=100, deadline=None)
def test_edge_case_thresholds(threshold):
    """
    Property 6: Edge case thresholds (0.0, 0.5, 1.0) work correctly.

    - threshold=0.0: all values should pass
    - threshold=1.0: only confidence=1.0 should pass (none in our system)
    - threshold=0.5: default behavior
    """
    metadata = {
        "low": ExtractionMetadata(value=1.0, confidence=0.3, source="derived"),
        "medium": ExtractionMetadata(value=2.0, confidence=0.5, source="text_regex"),
        "high": ExtractionMetadata(value=3.0, confidence=0.9, source="table_exact"),
    }

    filtered, _ = _apply_confidence_filter(metadata, threshold=threshold)

    if threshold == 0.0:
        # All should pass (even 0.3 >= 0.0)
        assert all(v is not None for v in filtered.values())
    elif threshold == 1.0:
        # None should pass (max confidence in this sample is 0.9 and no overrides are present)
        assert all(v is None for v in filtered.values())
    elif threshold == 0.5:
        # medium and high should pass, low should not
        assert filtered["low"] is None
        assert filtered["medium"] == 2.0
        assert filtered["high"] == 3.0


# =============================================================================
# Property 7: Valid PDF Metrics Don't Crash
# =============================================================================


@given(
    st.dictionaries(
        keys=st.sampled_from(
            [
                "revenue",
                "net_profit",
                "total_assets",
                "equity",
                "liabilities",
                "current_assets",
                "accounts_receivable",
            ]
        ),
        values=st.floats(min_value=0, max_value=1e12),
        min_size=1,
        max_size=15,
    )
)
@settings(max_examples=100, deadline=None)
def test_valid_pdf_metrics_dont_crash(metric_values):
    """
    Property 7: For ANY valid PDF metric values, the system doesn't crash
    and produces valid confidence scores.

    This simulates real-world usage with typical financial metrics.
    """
    # Simulate extraction with various sources
    metadata = {}
    sources = ["table_exact", "table_partial", "text_regex", "derived"]

    for i, (key, value) in enumerate(metric_values.items()):
        source = sources[i % len(sources)]
        confidence_map = {
            "table_exact": 0.9,
            "table_partial": 0.7,
            "text_regex": 0.5,
            "derived": 0.35,
        }
        confidence = confidence_map[source]
        metadata[key] = ExtractionMetadata(
            value=value, confidence=confidence, source=source
        )

    # Should not crash
    filtered, extraction_metadata = _apply_confidence_filter(metadata)

    # All keys should be present
    assert len(filtered) == len(metadata)
    assert len(extraction_metadata) == len(metadata)

    # Values should be either original or None
    for key in filtered:
        if filtered[key] is not None:
            assert filtered[key] == metric_values[key]


# =============================================================================
# Property 8: None Values Always Preserved
# =============================================================================


@given(
    st.dictionaries(keys=METRIC_NAME, values=CONFIDENCE_FLOAT, min_size=1, max_size=10),
    THRESHOLD_FLOAT,
)
@settings(max_examples=100, deadline=None)
def test_none_values_always_preserved(confidences, threshold):
    """
    Property 8: For ANY confidences, None values are always preserved as None
    (regardless of confidence score).

    This ensures missing data is handled correctly.
    """
    metadata = {
        f"metric_{i}": ExtractionMetadata(value=None, confidence=conf, source="derived")
        for i, conf in enumerate(confidences.values())
    }

    filtered, _ = _apply_confidence_filter(metadata, threshold=threshold)

    # All None values should remain None
    assert all(
        v is None for v in filtered.values()
    ), "None values should always remain None after filtering"


# =============================================================================
# Property 9: Deterministic Results
# =============================================================================


@given(
    st.dictionaries(
        keys=METRIC_NAME,
        values=st.tuples(CONFIDENCE_FLOAT, st.floats(-1e10, 1e10)),
        min_size=1,
        max_size=10,
    ),
    THRESHOLD_FLOAT,
)
@settings(max_examples=100, deadline=None)
def test_filtering_is_deterministic(metric_data, threshold):
    """
    Property 9: For ANY input, filtering is deterministic.

    Running the same filter twice should produce identical results.
    """
    metadata = {
        name: ExtractionMetadata(value=value, confidence=conf, source="table_exact")
        for name, (conf, value) in metric_data.items()
    }

    # Run twice
    filtered1, meta1 = _apply_confidence_filter(metadata, threshold=threshold)
    filtered2, meta2 = _apply_confidence_filter(metadata, threshold=threshold)

    # Results should be identical
    assert filtered1 == filtered2, "Filtering should be deterministic"
    assert meta1 == meta2, "Metadata output should be deterministic"
