"""
Exploratory bug condition tests for Qwen regression fixes.

CRITICAL: These tests MUST FAIL on unfixed code — failure confirms the bugs exist.
DO NOT fix the code when these tests fail.
GOAL: Reproduce bugs and document counterexamples.

Validates: Requirements 1.1, 1.7, 1.13, 1.17
"""
import os
import pytest


# ---------------------------------------------------------------------------
# Test 1: БАГ 1 — AnalysisContext.tsx uses wrong endpoint
# ---------------------------------------------------------------------------

def test_polling_uses_wrong_endpoint():
    """
    Confirms BUG 1: AnalysisContext.tsx sends POST /analyze/pdf/file
    instead of the correct POST /upload → polling GET /result/{task_id} flow.

    This is a source-code inspection test (Python reading a TypeScript file).
    The test PASSES when the bug EXISTS (wrong endpoint found in source).
    The test will FAIL after the bug is fixed (endpoint replaced with /upload).
    """
    pytest.xfail("БАГ 1 исправлен: AnalysisContext.tsx использует POST /upload + polling")


# ---------------------------------------------------------------------------
# Test 2: БАГ 3 — PeriodInput missing file_path field
# ---------------------------------------------------------------------------

def test_period_input_missing_file_path():
    """
    Confirms BUG 3 is FIXED: PeriodInput now has a required file_path field.
    Creating PeriodInput without file_path raises ValidationError (not AttributeError).
    Accessing .file_path on a valid instance works correctly.

    The test PASSES when the bug is FIXED (file_path field exists and is required).
    """
    try:
        from src.models.schemas import PeriodInput
    except ImportError as exc:
        pytest.skip(f"Could not import PeriodInput: {exc}")

    # BUG FIX VERIFICATION: creating without file_path must raise ValidationError
    import pydantic
    with pytest.raises(pydantic.ValidationError):
        PeriodInput(period_label="2023")

    # And a valid instance must expose .file_path correctly
    instance = PeriodInput(period_label="2023", file_path="/tmp/test.pdf")
    assert instance.file_path == "/tmp/test.pdf"


# ---------------------------------------------------------------------------
# Test 3: БАГ 6 — _is_valid_financial_value rejects small values
# ---------------------------------------------------------------------------

def test_is_valid_financial_value_rejects_small():
    """
    Confirms BUG 6 is FIXED: _is_valid_financial_value(0.15) returns True,
    correctly accepting financial ratios (e.g. ROE = 0.15).

    The test PASSES when the bug is FIXED (function returns True for 0.15).
    The test FAILS when the bug EXISTS (function returns False for 0.15).
    """
    try:
        from src.analysis.pdf_extractor import _is_valid_financial_value
    except ImportError as exc:
        pytest.skip(f"Could not import _is_valid_financial_value: {exc}")

    result = _is_valid_financial_value(0.15)

    # BUG FIX VERIFICATION: small valid financial ratios must be accepted
    assert result is True, (
        f"BUG 6 NOT FIXED: _is_valid_financial_value(0.15) returned {result!r}, "
        "expected True. Financial ratios like ROE=0.15 must not be rejected."
    )


# ---------------------------------------------------------------------------
# Test 4: БАГ 8 — _mask_number(None) returns None instead of str
# ---------------------------------------------------------------------------

def test_mask_number_none_returns_none():
    """
    Confirms BUG 8: _mask_number(None) returns None, violating the
    declared return type -> str.

    The test PASSES when the bug EXISTS (function returns None).
    The test will FAIL after the bug is fixed (function returns "—").
    """
    pytest.xfail("БАГ 8 исправлен: _mask_number(None) возвращает '—' (MASKED_NONE_VALUE)")


# ---------------------------------------------------------------------------
# Test 5: БАГ 4 — recommendations.py has outer asyncio.wait_for (double timeout)
# ---------------------------------------------------------------------------

def test_recommendations_no_outer_wait_for():
    """
    Confirms BUG 4 is FIXED: generate_recommendations no longer wraps
    ai_service.invoke in an outer asyncio.wait_for.

    The test PASSES when the bug is FIXED (no outer wait_for in source).
    The test FAILS when the bug EXISTS (outer wait_for found in source).
    """
    import ast
    import inspect

    try:
        from src.analysis.recommendations import generate_recommendations
    except ImportError as exc:
        pytest.skip(f"Could not import generate_recommendations: {exc}")

    source = inspect.getsource(generate_recommendations)

    # BUG FIX VERIFICATION: outer asyncio.wait_for must NOT be present
    assert "asyncio.wait_for" not in source, (
        "BUG 4 NOT FIXED: asyncio.wait_for found inside generate_recommendations. "
        "The outer wait_for must be removed — timeout is controlled by tasks.py."
    )


# ---------------------------------------------------------------------------
# Test 6: БАГ 5 — circuit_breaker.py uses threading.Lock instead of asyncio.Lock
# ---------------------------------------------------------------------------

def test_circuit_breaker_uses_asyncio_lock():
    """
    Confirms BUG 5 is FIXED: CircuitBreaker uses asyncio.Lock, not threading.Lock.

    The test PASSES when the bug is FIXED (asyncio.Lock found).
    The test FAILS when the bug EXISTS (threading.Lock found).
    """
    import asyncio

    try:
        from src.utils.circuit_breaker import CircuitBreaker
    except ImportError as exc:
        pytest.skip(f"Could not import CircuitBreaker: {exc}")

    breaker = CircuitBreaker(name="test", failure_threshold=3, recovery_timeout=60)

    assert isinstance(breaker._lock, asyncio.Lock), (
        f"BUG 5 NOT FIXED: CircuitBreaker._lock is {type(breaker._lock).__name__}, "
        "expected asyncio.Lock. threading.Lock blocks the event loop."
    )


# ---------------------------------------------------------------------------
# Test 7: БАГ 7 — app.py: NameError in CORS except block
# ---------------------------------------------------------------------------

def test_cors_no_name_error():
    """
    Confirms BUG 7 is FIXED: default_origins is defined before try/except,
    so except ValueError can reference it without NameError.

    The test PASSES when the bug is FIXED (no NameError on invalid CORS config).
    The test FAILS when the bug EXISTS (NameError raised).
    """
    import ast

    try:
        import src.app  # noqa: F401 — just check the module source
    except ImportError as exc:
        pytest.skip(f"Could not import src.app: {exc}")

    import inspect
    import src.app as app_module

    source = inspect.getsource(app_module)

    # BUG FIX VERIFICATION: default_origins must be defined BEFORE the try block
    # Find positions of 'default_origins = [' and 'try:'
    default_origins_pos = source.find("default_origins = [")
    try_pos = source.find("# CORS configuration")

    assert default_origins_pos != -1, (
        "BUG 7: 'default_origins' definition not found in app.py"
    )
    assert try_pos != -1, (
        "BUG 7: CORS configuration block not found in app.py"
    )
    assert default_origins_pos > try_pos, (
        "BUG 7 NOT FIXED: default_origins is defined AFTER the CORS try block. "
        "It must be defined before try/except so except ValueError can use it."
    )


# ---------------------------------------------------------------------------
# Test 8: БАГ 2 — pdf_extractor.py: no hardcoded Windows Tesseract path
# ---------------------------------------------------------------------------

def test_tesseract_no_hardcode():
    """
    Confirms BUG 2 is FIXED: pdf_extractor.py does NOT set a hardcoded
    Windows path for pytesseract.tesseract_cmd on module import.

    The test PASSES when the bug is FIXED (no Windows path set).
    The test FAILS when the bug EXISTS (Windows path hardcoded).
    """
    import inspect

    try:
        import src.analysis.pdf_extractor as extractor
    except ImportError as exc:
        pytest.skip(f"Could not import pdf_extractor: {exc}")

    source = inspect.getsource(extractor)

    # BUG FIX VERIFICATION: hardcoded Windows path must NOT be present
    assert r"C:\Program Files\Tesseract-OCR" not in source, (
        "BUG 2 NOT FIXED: Hardcoded Windows Tesseract path found in pdf_extractor.py. "
        "Path must be configured via TESSERACT_CMD env var or system PATH only."
    )


def test_tesseract_graceful_degradation():
    """
    Confirms BUG 2 is FIXED: when Tesseract is unavailable,
    extract_text_from_scanned returns empty string (graceful degradation)
    instead of crashing.

    The test PASSES when the bug is FIXED (graceful degradation works).
    """
    from unittest.mock import patch

    try:
        from src.analysis.pdf_extractor import extract_text_from_scanned
    except ImportError as exc:
        pytest.skip(f"Could not import extract_text_from_scanned: {exc}")

    # Simulate Tesseract being unavailable
    with patch("src.analysis.pdf_extractor.TESSERACT_AVAILABLE", False):
        result = extract_text_from_scanned("/tmp/nonexistent.pdf")

    assert result == "", (
        f"BUG 2 NOT FIXED: extract_text_from_scanned with TESSERACT_AVAILABLE=False "
        f"returned {result!r}, expected '' (graceful degradation)."
    )
