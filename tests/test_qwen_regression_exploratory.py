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
    frontend_file = os.path.join(
        os.path.dirname(__file__),
        "..",
        "frontend",
        "src",
        "context",
        "AnalysisContext.tsx",
    )
    frontend_file = os.path.normpath(frontend_file)

    assert os.path.exists(frontend_file), (
        f"Frontend file not found: {frontend_file}"
    )

    with open(frontend_file, encoding="utf-8") as f:
        content = f.read()

    # BUG CONDITION: the wrong endpoint must be present in the source
    assert "/analyze/pdf/file" in content, (
        "BUG 1 NOT REPRODUCED: '/analyze/pdf/file' not found in AnalysisContext.tsx. "
        "The bug may already be fixed."
    )


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
    Confirms BUG 6: _is_valid_financial_value(0.15) returns False,
    incorrectly rejecting financial ratios (e.g. ROE = 0.15).

    The test PASSES when the bug EXISTS (function returns False for 0.15).
    The test will FAIL after the bug is fixed (function returns True for 0.15).
    """
    try:
        from src.analysis.pdf_extractor import _is_valid_financial_value
    except ImportError as exc:
        pytest.skip(f"Could not import _is_valid_financial_value: {exc}")

    result = _is_valid_financial_value(0.15)

    # BUG CONDITION: the function incorrectly returns False for small valid values
    assert result is False, (
        f"BUG 6 NOT REPRODUCED: _is_valid_financial_value(0.15) returned {result!r}, "
        "expected False (the bug). The bug may already be fixed."
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
    try:
        from src.utils.masking import _mask_number
    except ImportError as exc:
        pytest.skip(f"Could not import _mask_number: {exc}")

    result = _mask_number(None)

    # BUG CONDITION: the function returns None instead of a string
    assert result is None, (
        f"BUG 8 NOT REPRODUCED: _mask_number(None) returned {result!r}, "
        "expected None (the bug). The bug may already be fixed."
    )
