"""
Preservation Tests for Qwen Regression Fixes

These tests MUST PASS before and after bugfixes. They verify that existing
correct behavior is preserved. If any of these tests fail after a fix,
it indicates a regression.

Property-based tests use Hypothesis to generate random inputs within valid ranges.

Validates: Requirements 3.1, 3.2, 3.4, 3.5, 3.6, 3.7, 3.11, 3.12
"""
import asyncio
import os
import pytest

from hypothesis import given, settings, assume
from hypothesis import strategies as st


# ---------------------------------------------------------------------------
# Test 1: prop_financial_value_filter (Property-based)
# ---------------------------------------------------------------------------

@given(
    st.one_of(
        # Large values within the current parser sanity bound (> 1000, not years)
        st.floats(min_value=1001.0, max_value=1e13 - 1, allow_nan=False, allow_infinity=False),
        # Small values (0 < v < 1000) — financial ratios, small business metrics
        st.floats(min_value=0.001, max_value=999.99, allow_nan=False, allow_infinity=False),
        # Negative values (losses, liabilities) within the same sanity bound
        st.floats(min_value=-(1e13 - 1), max_value=-0.001, allow_nan=False, allow_infinity=False),
    )
)
@settings(max_examples=300, deadline=None)
def test_prop_financial_value_filter(v: float) -> None:
    """
    Property: _is_valid_financial_value(v) == True for all v in (-1e13, 1e13)
    that are not integers in the year range 1900-2100.

    After the fix, this covers small values (ratios, small business) too.

    Validates: Requirement 3.1, 2.16, 2.17
    """
    try:
        from src.analysis.pdf_extractor import _is_valid_financial_value
    except ImportError as exc:
        pytest.skip("Could not import _is_valid_financial_value: %s" % exc)

    # Exclude year-range integers (1900-2100) — those are legitimately rejected
    assume(not (v == int(v) and 1900 <= int(v) <= 2100))
    # Exclude float representations of years (e.g. 2023.0)
    assume(not (isinstance(v, float) and v.is_integer() and 1900 <= int(v) <= 2100))

    result = _is_valid_financial_value(v)
    assert result is True, (
        "REGRESSION: _is_valid_financial_value(%r) returned %r, expected True. "
        "Financial values must be accepted regardless of magnitude." % (v, result)
    )


# ---------------------------------------------------------------------------
# Test 2: prop_masking_idempotency (Property-based)
# ---------------------------------------------------------------------------

@given(
    st.dictionaries(
        keys=st.text(min_size=1, max_size=20),
        values=st.one_of(
            st.integers(min_value=-10_000_000, max_value=10_000_000),
            st.floats(
                min_value=-1e9,
                max_value=1e9,
                allow_nan=False,
                allow_infinity=False,
            ),
        ),
        min_size=0,
        max_size=10,
    )
)
@settings(max_examples=100)
def test_prop_masking_idempotency(values: dict) -> None:
    """
    Property: mask_analysis_data applied twice equals applied once.

    mask_analysis_data(mask_analysis_data(data, True), True) == mask_analysis_data(data, True)

    Validates: Requirement 3.5
    """
    try:
        from src.utils.masking import mask_analysis_data
    except ImportError as exc:
        pytest.skip("Could not import mask_analysis_data: %s" % exc)

    data = {"data": {"metrics": values, "ratios": {}}}

    once = mask_analysis_data(data, True)
    twice = mask_analysis_data(once, True)

    assert once == twice, (
        "REGRESSION: mask_analysis_data is not idempotent. "
        "Applying twice changed the result.\nOnce: %r\nTwice: %r" % (once, twice)
    )


# ---------------------------------------------------------------------------
# Test 3: prop_circuit_breaker_state_machine (Property-based)
# ---------------------------------------------------------------------------

# Valid state transitions: (from_state, action) -> to_state
_VALID_TRANSITIONS = {
    ("CLOSED", "failure_at_threshold"): "OPEN",
    ("CLOSED", "success"): "CLOSED",
    ("CLOSED", "failure_below_threshold"): "CLOSED",
    ("HALF_OPEN", "success"): "CLOSED",
    ("HALF_OPEN", "failure"): "OPEN",
}


@given(
    st.lists(
        st.booleans(),  # True = success, False = failure
        min_size=1,
        max_size=20,
    )
)
@settings(max_examples=100)
def test_prop_circuit_breaker_state_machine(actions: list) -> None:
    """
    Property: CircuitBreaker state transitions follow the defined automaton.

    CLOSED -> OPEN when failure_count >= threshold
    OPEN -> HALF_OPEN after recovery_timeout (not tested here — time-dependent)
    HALF_OPEN -> CLOSED on success
    HALF_OPEN -> OPEN on failure

    Uses a low threshold (2) to trigger transitions quickly.

    Validates: Requirement 3.4
    """
    try:
        from src.utils.circuit_breaker import CircuitBreaker, CircuitState
    except ImportError as exc:
        pytest.skip("Could not import CircuitBreaker: %s" % exc)

    async def _run():
        threshold = 2
        breaker = CircuitBreaker(
            name="test",
            failure_threshold=threshold,
            recovery_timeout=9999,  # Prevent OPEN->HALF_OPEN during test
        )

        failure_count = 0

        for is_success in actions:
            state_before = breaker._state

            if is_success:
                await breaker.record_success()
                failure_count = max(0, failure_count - 1)
            else:
                await breaker.record_failure()
                failure_count += 1

            state_after = breaker._state

            # Validate: CLOSED -> OPEN only when threshold reached
            if state_before == CircuitState.CLOSED and state_after == CircuitState.OPEN:
                assert failure_count >= threshold, (
                    "REGRESSION: Circuit opened with only %d failures (threshold=%d)" % (
                        failure_count, threshold
                    )
                )

            # Validate: HALF_OPEN -> CLOSED only on success
            if state_before == CircuitState.HALF_OPEN and state_after == CircuitState.CLOSED:
                assert is_success, (
                    "REGRESSION: Circuit closed from HALF_OPEN on a failure"
                )

            # Validate: HALF_OPEN -> OPEN only on failure
            if state_before == CircuitState.HALF_OPEN and state_after == CircuitState.OPEN:
                assert not is_success, (
                    "REGRESSION: Circuit opened from HALF_OPEN on a success"
                )

            # Validate: no illegal transitions (CLOSED -> HALF_OPEN directly)
            assert not (
                state_before == CircuitState.CLOSED and state_after == CircuitState.HALF_OPEN
            ), "REGRESSION: Illegal transition CLOSED -> HALF_OPEN"

    asyncio.run(_run())


# ---------------------------------------------------------------------------
# Test 4: prop_polling_termination (Property-based / source inspection)
# ---------------------------------------------------------------------------

def test_prop_polling_termination() -> None:
    """
    Property: The polling logic in AnalysisContext.tsx must define MAX_POLLING_ATTEMPTS.

    On unfixed code this test may FAIL because the file uses a synchronous call
    instead of polling. If it fails, document the finding but do not fix the code.

    This is a source-inspection test (Python reading TypeScript).

    Validates: Requirement 3.11
    """
    frontend_file = os.path.normpath(
        os.path.join(
            os.path.dirname(__file__),
            "..",
            "frontend",
            "src",
            "context",
            "AnalysisContext.tsx",
        )
    )

    if not os.path.exists(frontend_file):
        pytest.skip("AnalysisContext.tsx not found: %s" % frontend_file)

    with open(frontend_file, encoding="utf-8") as fh:
        content = fh.read()

    # After the fix, MAX_POLLING_ATTEMPTS must be defined and polling must stop
    # On unfixed code this assertion will FAIL — document the finding
    assert "MAX_POLLING_ATTEMPTS" in content, (
        "PRESERVATION BASELINE MISSING: MAX_POLLING_ATTEMPTS not found in "
        "AnalysisContext.tsx. The polling termination guarantee is absent. "
        "This confirms BUG #1 is present (no polling flow)."
    )


# ---------------------------------------------------------------------------
# Test 5: test_large_financial_values_accepted (Unit)
# ---------------------------------------------------------------------------

def test_large_financial_values_accepted() -> None:
    """
    Large financial values (> 1000) must be accepted by _is_valid_financial_value.

    Validates: Requirement 3.1
    """
    try:
        from src.analysis.pdf_extractor import _is_valid_financial_value
    except ImportError as exc:
        pytest.skip("Could not import _is_valid_financial_value: %s" % exc)

    assert _is_valid_financial_value(1_000_000) is True, (
        "REGRESSION: _is_valid_financial_value(1_000_000) returned False"
    )
    assert _is_valid_financial_value(999_999_999) is True, (
        "REGRESSION: _is_valid_financial_value(999_999_999) returned False"
    )
    assert _is_valid_financial_value(1001.0) is True, (
        "REGRESSION: _is_valid_financial_value(1001.0) returned False"
    )


# ---------------------------------------------------------------------------
# Test 6: test_mask_number_numeric_values (Unit)
# ---------------------------------------------------------------------------

def test_mask_number_numeric_values() -> None:
    """
    _mask_number with numeric (non-None) values must return a non-None string.

    Validates: Requirement 3.5
    """
    try:
        from src.utils.masking import _mask_number
    except ImportError as exc:
        pytest.skip("Could not import _mask_number: %s" % exc)

    result = _mask_number(1234567.89)

    assert result is not None, (
        "REGRESSION: _mask_number(1234567.89) returned None"
    )
    assert isinstance(result, str), (
        "REGRESSION: _mask_number(1234567.89) returned %r (not str)" % type(result)
    )
    # The masked value should contain 'X' characters
    assert "X" in result, (
        "REGRESSION: _mask_number(1234567.89) returned %r — expected 'X' mask characters" % result
    )


# ---------------------------------------------------------------------------
# Test 7: test_cors_valid_config (Integration)
# ---------------------------------------------------------------------------

def test_cors_valid_config() -> None:
    """
    App with valid CORS_ALLOW_ORIGINS must configure CORS without exceptions.

    Validates: Requirement 3.6
    """
    try:
        from src.app import _parse_cors_origins
    except ImportError as exc:
        pytest.skip("Could not import _parse_cors_origins: %s" % exc)

    # Valid origins — must not raise
    origins = _parse_cors_origins("http://localhost,http://localhost:3000")

    assert isinstance(origins, list), (
        "REGRESSION: _parse_cors_origins returned %r instead of list" % type(origins)
    )
    assert "http://localhost" in origins, (
        "REGRESSION: http://localhost missing from parsed origins: %r" % origins
    )
    assert "http://localhost:3000" in origins, (
        "REGRESSION: http://localhost:3000 missing from parsed origins: %r" % origins
    )


# ---------------------------------------------------------------------------
# Test 8: test_recommendations_fallback (Unit)
# ---------------------------------------------------------------------------

def test_recommendations_fallback() -> None:
    """
    generate_recommendations must return FALLBACK_RECOMMENDATIONS when AI is unavailable.

    Validates: Requirement 3.7, 3.12
    """
    try:
        from src.analysis.recommendations import (
            generate_recommendations,
            FALLBACK_RECOMMENDATIONS,
        )
    except ImportError as exc:
        pytest.skip("Could not import recommendations module: %s" % exc)

    from unittest.mock import AsyncMock, patch

    async def _run() -> list:
        with patch(
            "src.analysis.recommendations.ai_service.invoke",
            new_callable=AsyncMock,
            side_effect=Exception("AI unavailable"),
        ):
            return await generate_recommendations(
                metrics={},
                ratios={},
                nlp_result={},
            )

    result = asyncio.run(_run())

    assert result == FALLBACK_RECOMMENDATIONS, (
        "REGRESSION: generate_recommendations did not return FALLBACK_RECOMMENDATIONS "
        "when AI is unavailable. Got: %r" % result
    )


# ---------------------------------------------------------------------------
# Test 9: test_tesseract_env_cmd_respected (Preservation — БАГ 2)
# ---------------------------------------------------------------------------

def test_tesseract_env_cmd_respected() -> None:
    """
    When TESSERACT_CMD env var is set, pdf_extractor must use it as the
    tesseract command path (not a hardcoded Windows path).

    Validates: Requirement 3.2
    """
    import importlib
    import sys
    from unittest.mock import patch

    # Reload the module with TESSERACT_CMD set to a custom path
    with patch.dict(os.environ, {"TESSERACT_CMD": "/usr/local/bin/tesseract"}):
        # Remove cached module to force re-import
        for mod_name in list(sys.modules.keys()):
            if "pdf_extractor" in mod_name:
                del sys.modules[mod_name]

        try:
            import pytesseract
            import src.analysis.pdf_extractor  # noqa: F401
            # After import, tesseract_cmd should be set to our env value
            assert pytesseract.pytesseract.tesseract_cmd == "/usr/local/bin/tesseract", (
                "REGRESSION: TESSERACT_CMD env var not respected. "
                "Got: %r" % pytesseract.pytesseract.tesseract_cmd
            )
        except ImportError as exc:
            pytest.skip("Could not import pdf_extractor: %s" % exc)
        finally:
            # Restore module state
            for mod_name in list(sys.modules.keys()):
                if "pdf_extractor" in mod_name:
                    del sys.modules[mod_name]
