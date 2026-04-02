"""
Fix Verification Tests for Qwen Regression Fixes

These tests verify that all 14 bugs introduced by Qwen are fixed.
They MUST PASS on the fixed code.

Validates: Requirements 2.1–2.26
"""
import asyncio
import inspect
import os
import pytest


# ---------------------------------------------------------------------------
# БАГ 1 — AnalysisContext.tsx: polling flow
# ---------------------------------------------------------------------------

def test_polling_uses_upload_endpoint():
    """POST /upload is used instead of /analyze/pdf/file. Req 2.1"""
    frontend_file = os.path.normpath(
        os.path.join(os.path.dirname(__file__), "..", "frontend", "src", "context", "AnalysisContext.tsx")
    )
    if not os.path.exists(frontend_file):
        pytest.skip("AnalysisContext.tsx not found")

    with open(frontend_file, encoding="utf-8") as f:
        content = f.read()

    assert "/upload" in content, "POST /upload not found in AnalysisContext.tsx"
    assert "/analyze/pdf/file" not in content, "Old wrong endpoint still present"


def test_polling_max_attempts_defined():
    """MAX_POLLING_ATTEMPTS remains explicitly bounded for polling flow. Req 2.4"""
    frontend_file = os.path.normpath(
        os.path.join(os.path.dirname(__file__), "..", "frontend", "src", "context", "AnalysisContext.tsx")
    )
    if not os.path.exists(frontend_file):
        pytest.skip("AnalysisContext.tsx not found")

    with open(frontend_file, encoding="utf-8") as f:
        content = f.read()

    assert "MAX_POLLING_ATTEMPTS" in content, "MAX_POLLING_ATTEMPTS not defined"
    assert "MAX_POLLING_ATTEMPTS = 600" in content, "MAX_POLLING_ATTEMPTS must stay explicit and bounded"


def test_polling_stops_on_404():
    """HTTP 404 stops polling. Req 2.3"""
    frontend_file = os.path.normpath(
        os.path.join(os.path.dirname(__file__), "..", "frontend", "src", "context", "AnalysisContext.tsx")
    )
    if not os.path.exists(frontend_file):
        pytest.skip("AnalysisContext.tsx not found")

    with open(frontend_file, encoding="utf-8") as f:
        content = f.read()

    assert "404" in content, "404 handling not found in AnalysisContext.tsx"


def test_polling_retries_on_5xx():
    """HTTP 5xx triggers retry. Req 2.4"""
    frontend_file = os.path.normpath(
        os.path.join(os.path.dirname(__file__), "..", "frontend", "src", "context", "AnalysisContext.tsx")
    )
    if not os.path.exists(frontend_file):
        pytest.skip("AnalysisContext.tsx not found")

    with open(frontend_file, encoding="utf-8") as f:
        content = f.read()

    assert ">= 500" in content or ">= 500" in content or "5xx" in content or "httpStatus >= 500" in content, \
        "5xx retry logic not found in AnalysisContext.tsx"


# ---------------------------------------------------------------------------
# БАГ 2 — pdf_extractor.py: Tesseract
# ---------------------------------------------------------------------------

def test_tesseract_no_hardcode():
    """No hardcoded Windows Tesseract path. Req 2.6"""
    try:
        import src.analysis.pdf_extractor as extractor
    except ImportError as exc:
        pytest.skip("Could not import pdf_extractor: %s" % exc)

    source = inspect.getsource(extractor)
    assert r"C:\Program Files\Tesseract-OCR" not in source, \
        "Hardcoded Windows Tesseract path still present in pdf_extractor.py"


def test_tesseract_graceful_degradation():
    """TESSERACT_AVAILABLE=False → empty string, no crash. Req 2.8"""
    from unittest.mock import patch

    try:
        from src.analysis.pdf_extractor import extract_text_from_scanned
    except ImportError as exc:
        pytest.skip("Could not import extract_text_from_scanned: %s" % exc)

    with patch("src.analysis.pdf_extractor.TESSERACT_AVAILABLE", False):
        result = extract_text_from_scanned("/tmp/nonexistent.pdf")

    assert result == "", \
        "extract_text_from_scanned with TESSERACT_AVAILABLE=False returned %r, expected ''" % result


# ---------------------------------------------------------------------------
# БАГ 3 — PeriodInput.file_path
# ---------------------------------------------------------------------------

def test_period_input_has_file_path():
    """PeriodInput accepts file_path. Req 2.9"""
    try:
        from src.models.schemas import PeriodInput
    except ImportError as exc:
        pytest.skip("Could not import PeriodInput: %s" % exc)

    instance = PeriodInput(period_label="2023", file_path="/tmp/test.pdf")
    assert instance.file_path == "/tmp/test.pdf"


def test_multi_analysis_validates_file_count():
    """len(files) != len(periods) → 422. Req 2.11"""
    try:
        from src.routers.multi_analysis import router  # noqa: F401
    except ImportError as exc:
        pytest.skip("Could not import multi_analysis router: %s" % exc)

    source = inspect.getsource(router.__class__)
    # Check via source of the module
    import src.routers.multi_analysis as ma_module
    ma_source = inspect.getsource(ma_module)
    assert "422" in ma_source or "len(files) != len(periods)" in ma_source, \
        "File count validation (422) not found in multi_analysis router"


# ---------------------------------------------------------------------------
# БАГ 4 — recommendations.py: no double timeout
# ---------------------------------------------------------------------------

def test_recommendations_no_outer_wait_for():
    """No asyncio.wait_for inside generate_recommendations. Req 2.12"""
    try:
        from src.analysis.recommendations import generate_recommendations
    except ImportError as exc:
        pytest.skip("Could not import generate_recommendations: %s" % exc)

    source = inspect.getsource(generate_recommendations)
    assert "asyncio.wait_for" not in source, \
        "asyncio.wait_for found inside generate_recommendations — double timeout bug not fixed"


# ---------------------------------------------------------------------------
# БАГ 5 — circuit_breaker.py: asyncio.Lock
# ---------------------------------------------------------------------------

def test_circuit_breaker_uses_asyncio_lock():
    """CircuitBreaker uses asyncio.Lock. Req 2.14"""
    import asyncio as _asyncio

    try:
        from src.utils.circuit_breaker import CircuitBreaker
    except ImportError as exc:
        pytest.skip("Could not import CircuitBreaker: %s" % exc)

    breaker = CircuitBreaker(name="test", failure_threshold=3, recovery_timeout=60)
    assert isinstance(breaker._lock, _asyncio.Lock), \
        "CircuitBreaker._lock is %s, expected asyncio.Lock" % type(breaker._lock).__name__


def test_circuit_breaker_record_methods_are_async():
    """record_success/failure/reset are async. Req 2.14"""
    try:
        from src.utils.circuit_breaker import CircuitBreaker
    except ImportError as exc:
        pytest.skip("Could not import CircuitBreaker: %s" % exc)

    assert asyncio.iscoroutinefunction(CircuitBreaker.record_success), \
        "record_success must be async"
    assert asyncio.iscoroutinefunction(CircuitBreaker.record_failure), \
        "record_failure must be async"
    assert asyncio.iscoroutinefunction(CircuitBreaker.reset), \
        "reset must be async"


# ---------------------------------------------------------------------------
# БАГ 6 — _is_valid_financial_value
# ---------------------------------------------------------------------------

def test_is_valid_financial_value_accepts_small():
    """_is_valid_financial_value(0.15) → True. Req 2.16"""
    try:
        from src.analysis.pdf_extractor import _is_valid_financial_value
    except ImportError as exc:
        pytest.skip("Could not import _is_valid_financial_value: %s" % exc)

    assert _is_valid_financial_value(0.15) is True, \
        "_is_valid_financial_value(0.15) returned False — financial ratios must be accepted"
    assert _is_valid_financial_value(500) is True, \
        "_is_valid_financial_value(500) returned False — small business values must be accepted"
    assert _is_valid_financial_value(1.5) is True, \
        "_is_valid_financial_value(1.5) returned False — current_ratio must be accepted"


def test_is_valid_financial_value_rejects_year():
    """_is_valid_financial_value(2023) → False. Req 2.16"""
    try:
        from src.analysis.pdf_extractor import _is_valid_financial_value
    except ImportError as exc:
        pytest.skip("Could not import _is_valid_financial_value: %s" % exc)

    assert _is_valid_financial_value(2023) is False, \
        "_is_valid_financial_value(2023) returned True — year values must be rejected"
    assert _is_valid_financial_value(1900) is False, \
        "_is_valid_financial_value(1900) returned True — year values must be rejected"
    assert _is_valid_financial_value(2100) is False, \
        "_is_valid_financial_value(2100) returned True — year values must be rejected"


def test_is_valid_financial_value_float_year():
    """_is_valid_financial_value(2023.0) → False (safe float comparison). Req 2.16"""
    try:
        from src.analysis.pdf_extractor import _is_valid_financial_value
    except ImportError as exc:
        pytest.skip("Could not import _is_valid_financial_value: %s" % exc)

    assert _is_valid_financial_value(2023.0) is False, \
        "_is_valid_financial_value(2023.0) returned True — float years must be rejected"


# ---------------------------------------------------------------------------
# БАГ 7 — app.py: CORS NameError
# ---------------------------------------------------------------------------

def test_cors_no_name_error():
    """default_origins defined before try/except. Req 2.18"""
    try:
        import src.app as app_module
    except ImportError as exc:
        pytest.skip("Could not import src.app: %s" % exc)

    source = inspect.getsource(app_module)

    default_origins_pos = source.find("default_origins = [")
    cors_section_pos = source.find("# CORS configuration")

    assert default_origins_pos != -1, "default_origins definition not found in app.py"
    assert cors_section_pos != -1, "CORS configuration section not found in app.py"
    # default_origins must be defined BEFORE the CORS try block
    assert default_origins_pos > cors_section_pos, \
        "default_origins must be defined before the CORS try/except block"


# ---------------------------------------------------------------------------
# БАГ 8 — masking.py: _mask_number(None) → "—"
# ---------------------------------------------------------------------------

def test_mask_number_none_returns_dash():
    """_mask_number(None) → '—'. Req 2.19"""
    try:
        from src.utils.masking import _mask_number, MASKED_NONE_VALUE
    except ImportError as exc:
        pytest.skip("Could not import _mask_number: %s" % exc)

    result = _mask_number(None)
    assert result == "—", "_mask_number(None) returned %r, expected '—'" % result
    assert result == MASKED_NONE_VALUE, \
        "_mask_number(None) must return MASKED_NONE_VALUE constant"
    assert isinstance(result, str), \
        "_mask_number(None) must return str, got %s" % type(result).__name__


# ---------------------------------------------------------------------------
# БАГ 9 — no f-strings in loggers
# ---------------------------------------------------------------------------

def test_no_fstrings_in_loggers_app():
    """No f-strings in logger calls in app.py. Req 2.21"""
    import re
    try:
        import src.app as m
    except ImportError as exc:
        pytest.skip("Could not import src.app: %s" % exc)

    source = inspect.getsource(m)
    matches = re.findall(r'logger\.\w+\(f"', source)
    assert not matches, "f-strings in logger calls found in app.py: %s" % matches


def test_no_fstrings_in_loggers_tasks():
    """No f-strings in logger calls in tasks.py. Req 2.21"""
    import re
    try:
        import src.tasks as m
    except ImportError as exc:
        pytest.skip("Could not import src.tasks: %s" % exc)

    source = inspect.getsource(m)
    matches = re.findall(r'logger\.\w+\(f"', source)
    assert not matches, "f-strings in logger calls found in tasks.py: %s" % matches


def test_no_fstrings_in_loggers_retry_utils():
    """No f-strings in logger calls in retry_utils.py. Req 2.21"""
    import re
    try:
        import src.utils.retry_utils as m
    except ImportError as exc:
        pytest.skip("Could not import src.utils.retry_utils: %s" % exc)

    source = inspect.getsource(m)
    matches = re.findall(r'logger\.\w+\(f"', source)
    assert not matches, "f-strings in logger calls found in retry_utils.py: %s" % matches


# ---------------------------------------------------------------------------
# БАГ 10 — tasks.py: module-level imports
# ---------------------------------------------------------------------------

def test_tasks_no_inline_imports():
    """No inline imports inside functions in tasks.py. Req 2.22"""
    import re
    try:
        import src.tasks as m
    except ImportError as exc:
        pytest.skip("Could not import src.tasks: %s" % exc)

    source = inspect.getsource(m)
    # Find indented 'from src.' imports (inside functions)
    inline = re.findall(r'^\s{4,}from src\.', source, re.MULTILINE)
    assert not inline, "Inline imports found inside functions in tasks.py: %s" % inline


def test_tasks_module_level_imports():
    """analyze_narrative, generate_recommendations, _extract_metrics_with_regex at module level. Req 2.22"""
    try:
        import src.tasks as m
    except ImportError as exc:
        pytest.skip("Could not import src.tasks: %s" % exc)

    assert hasattr(m, "analyze_narrative_with_runtime"), "analyze_narrative_with_runtime not imported at module level"
    assert hasattr(m, "generate_recommendations"), "generate_recommendations not imported at module level"
    assert hasattr(m, "_extract_metrics_with_regex"), "_extract_metrics_with_regex not imported at module level"


# ---------------------------------------------------------------------------
# БАГ 11 — requirements.txt: pdfplumber version
# ---------------------------------------------------------------------------

def test_table_extraction_dependencies_declared():
    """Current table-extraction stack is declared in requirements. Req 2.23"""
    req_file = os.path.normpath(
        os.path.join(os.path.dirname(__file__), "..", "requirements.txt")
    )
    if not os.path.exists(req_file):
        pytest.skip("requirements.txt not found")

    with open(req_file, encoding="utf-8") as f:
        content = f.read()

    assert "camelot-py~=0.11.0" in content, \
        "camelot-py requirement missing from requirements.txt"
    assert "pdfplumber" not in content, \
        "requirements.txt still contains stale pdfplumber dependency"


# ---------------------------------------------------------------------------
# БАГ 12 — client.ts: conditional console.log
# ---------------------------------------------------------------------------

def test_client_ts_conditional_log():
    """console.log/error wrapped in import.meta.env.DEV. Req 2.24"""
    client_file = os.path.normpath(
        os.path.join(os.path.dirname(__file__), "..", "frontend", "src", "api", "client.ts")
    )
    if not os.path.exists(client_file):
        pytest.skip("client.ts not found")

    with open(client_file, encoding="utf-8") as f:
        content = f.read()

    # All console.log/error must be inside DEV guard
    import re
    # Find console.log/error lines NOT preceded by DEV check
    lines = content.splitlines()
    for i, line in enumerate(lines):
        if "console.log" in line or "console.error" in line:
            # Check surrounding context for DEV guard
            context = "\n".join(lines[max(0, i - 3):i + 1])
            assert "import.meta.env.DEV" in context, \
                "console.log/error on line %d not wrapped in import.meta.env.DEV check:\n%s" % (i + 1, context)


# ---------------------------------------------------------------------------
# БАГ 13 — TypeScript: no err: any
# ---------------------------------------------------------------------------

def test_no_err_any_in_analysis_context():
    """No 'err: any' in AnalysisContext.tsx. Req 2.25"""
    frontend_file = os.path.normpath(
        os.path.join(os.path.dirname(__file__), "..", "frontend", "src", "context", "AnalysisContext.tsx")
    )
    if not os.path.exists(frontend_file):
        pytest.skip("AnalysisContext.tsx not found")

    with open(frontend_file, encoding="utf-8") as f:
        content = f.read()

    assert "err: any" not in content and "e: any" not in content, \
        "err: any / e: any found in AnalysisContext.tsx — must use unknown"


def test_no_err_any_in_analysis_history():
    """No 'e: any' in AnalysisHistory.tsx. Req 2.25"""
    frontend_file = os.path.normpath(
        os.path.join(os.path.dirname(__file__), "..", "frontend", "src", "pages", "AnalysisHistory.tsx")
    )
    if not os.path.exists(frontend_file):
        pytest.skip("AnalysisHistory.tsx not found")

    with open(frontend_file, encoding="utf-8") as f:
        content = f.read()

    assert "e: any" not in content and "err: any" not in content, \
        "e: any / err: any found in AnalysisHistory.tsx — must use unknown"


# ---------------------------------------------------------------------------
# БАГ 14 — docs/CONFIGURATION.md: актуальные AI-провайдеры
# ---------------------------------------------------------------------------

def test_configuration_md_no_deepseek_provider():
    """CONFIGURATION.md does not describe DeepSeek as primary provider. Req 2.26"""
    docs_file = os.path.normpath(
        os.path.join(os.path.dirname(__file__), "..", "docs", "CONFIGURATION.md")
    )
    if not os.path.exists(docs_file):
        pytest.skip("docs/CONFIGURATION.md not found")

    with open(docs_file, encoding="utf-8") as f:
        content = f.read()

    assert "HuggingFace" in content, "HuggingFace not mentioned in CONFIGURATION.md"
    assert "Qwen" in content, "Qwen not mentioned in CONFIGURATION.md"
    assert "HF_TOKEN" in content, "HF_TOKEN not documented in CONFIGURATION.md"
    assert "HF_MODEL" in content, "HF_MODEL not documented in CONFIGURATION.md"
    # DeepSeek must not be the section header for priority 2 provider
    assert "#### DeepSeek" not in content, \
        "DeepSeek still listed as primary provider section in CONFIGURATION.md"
