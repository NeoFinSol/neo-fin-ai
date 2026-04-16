"""
Tests for AppSettings AI runtime field validators (F5).

Covers: ai_timeout [1,600], ai_retry_count [0,10], ai_retry_backoff [0.1,60.0]
Each field: at-min, at-max, below-min, above-max, non-numeric string, None,
            and a valid mid-range value.
PBT: Hypothesis properties that invalid inputs always return the default.
"""

import pytest
from hypothesis import given, settings as h_settings
from hypothesis import strategies as st

from src.models.settings import AppSettings

_ENV_NONE = {"_env_file": None}


# ---------------------------------------------------------------------------
# ai_timeout
# ---------------------------------------------------------------------------


class TestAiTimeoutValidator:
    def test_at_min(self):
        s = AppSettings(AI_TIMEOUT=1, **_ENV_NONE)
        assert s.ai_timeout == 1

    def test_at_max(self):
        s = AppSettings(AI_TIMEOUT=600, **_ENV_NONE)
        assert s.ai_timeout == 600

    def test_below_min_returns_default(self):
        s = AppSettings(AI_TIMEOUT=0, **_ENV_NONE)
        assert s.ai_timeout == 120

    def test_negative_returns_default(self):
        s = AppSettings(AI_TIMEOUT=-1, **_ENV_NONE)
        assert s.ai_timeout == 120

    def test_above_max_returns_default(self):
        s = AppSettings(AI_TIMEOUT=601, **_ENV_NONE)
        assert s.ai_timeout == 120

    def test_non_numeric_string_returns_default(self):
        s = AppSettings(AI_TIMEOUT="bad", **_ENV_NONE)
        assert s.ai_timeout == 120

    def test_none_returns_default(self):
        s = AppSettings(AI_TIMEOUT=None, **_ENV_NONE)
        assert s.ai_timeout == 120

    def test_valid_mid_range(self):
        s = AppSettings(AI_TIMEOUT=300, **_ENV_NONE)
        assert s.ai_timeout == 300

    def test_string_numeric_accepted(self):
        s = AppSettings(AI_TIMEOUT="60", **_ENV_NONE)
        assert s.ai_timeout == 60


# ---------------------------------------------------------------------------
# ai_retry_count
# ---------------------------------------------------------------------------


class TestAiRetryCountValidator:
    def test_at_min_zero(self):
        s = AppSettings(AI_RETRY_COUNT=0, **_ENV_NONE)
        assert s.ai_retry_count == 0

    def test_at_max(self):
        s = AppSettings(AI_RETRY_COUNT=10, **_ENV_NONE)
        assert s.ai_retry_count == 10

    def test_below_min_returns_default(self):
        s = AppSettings(AI_RETRY_COUNT=-1, **_ENV_NONE)
        assert s.ai_retry_count == 2

    def test_above_max_returns_default(self):
        s = AppSettings(AI_RETRY_COUNT=11, **_ENV_NONE)
        assert s.ai_retry_count == 2

    def test_non_numeric_string_returns_default(self):
        s = AppSettings(AI_RETRY_COUNT="many", **_ENV_NONE)
        assert s.ai_retry_count == 2

    def test_none_returns_default(self):
        s = AppSettings(AI_RETRY_COUNT=None, **_ENV_NONE)
        assert s.ai_retry_count == 2

    def test_valid_mid_range(self):
        s = AppSettings(AI_RETRY_COUNT=5, **_ENV_NONE)
        assert s.ai_retry_count == 5

    def test_string_numeric_accepted(self):
        s = AppSettings(AI_RETRY_COUNT="3", **_ENV_NONE)
        assert s.ai_retry_count == 3


# ---------------------------------------------------------------------------
# ai_retry_backoff
# ---------------------------------------------------------------------------


class TestAiRetryBackoffValidator:
    def test_at_min(self):
        s = AppSettings(AI_RETRY_BACKOFF=0.1, **_ENV_NONE)
        assert s.ai_retry_backoff == pytest.approx(0.1)

    def test_at_max(self):
        s = AppSettings(AI_RETRY_BACKOFF=60.0, **_ENV_NONE)
        assert s.ai_retry_backoff == pytest.approx(60.0)

    def test_below_min_returns_default(self):
        s = AppSettings(AI_RETRY_BACKOFF=0.0, **_ENV_NONE)
        assert s.ai_retry_backoff == pytest.approx(2.0)

    def test_negative_returns_default(self):
        s = AppSettings(AI_RETRY_BACKOFF=-1.0, **_ENV_NONE)
        assert s.ai_retry_backoff == pytest.approx(2.0)

    def test_above_max_returns_default(self):
        s = AppSettings(AI_RETRY_BACKOFF=60.1, **_ENV_NONE)
        assert s.ai_retry_backoff == pytest.approx(2.0)

    def test_non_numeric_string_returns_default(self):
        s = AppSettings(AI_RETRY_BACKOFF="fast", **_ENV_NONE)
        assert s.ai_retry_backoff == pytest.approx(2.0)

    def test_none_returns_default(self):
        s = AppSettings(AI_RETRY_BACKOFF=None, **_ENV_NONE)
        assert s.ai_retry_backoff == pytest.approx(2.0)

    def test_valid_mid_range(self):
        s = AppSettings(AI_RETRY_BACKOFF=5.0, **_ENV_NONE)
        assert s.ai_retry_backoff == pytest.approx(5.0)

    def test_string_numeric_accepted(self):
        s = AppSettings(AI_RETRY_BACKOFF="1.5", **_ENV_NONE)
        assert s.ai_retry_backoff == pytest.approx(1.5)


# ---------------------------------------------------------------------------
# PBT — Hypothesis property tests (2.6)
# ---------------------------------------------------------------------------


@given(
    st.one_of(
        st.integers(max_value=0),
        st.integers(min_value=601),
        st.text(min_size=1).filter(lambda s: not s.strip().lstrip("-").isdigit()),
    )
)
@h_settings(max_examples=50)
def test_ai_timeout_invalid_always_returns_default(v):
    """P1: for any out-of-range or non-numeric value, ai_timeout == 120."""
    s = AppSettings(AI_TIMEOUT=v, **_ENV_NONE)
    assert s.ai_timeout == 120


@given(
    st.one_of(
        st.integers(max_value=-1),
        st.integers(min_value=11),
        st.text(min_size=1).filter(lambda s: not s.strip().lstrip("-").isdigit()),
    )
)
@h_settings(max_examples=50)
def test_ai_retry_count_invalid_always_returns_default(v):
    """P1: for any out-of-range or non-numeric value, ai_retry_count == 2."""
    s = AppSettings(AI_RETRY_COUNT=v, **_ENV_NONE)
    assert s.ai_retry_count == 2


@given(
    st.one_of(
        st.floats(max_value=0.09, allow_nan=False, allow_infinity=False),
        st.floats(min_value=60.01, allow_nan=False, allow_infinity=False),
        st.text(min_size=1).filter(
            lambda s: not _is_numeric(s)
        ),
    )
)
@h_settings(max_examples=50)
def test_ai_retry_backoff_invalid_always_returns_default(v):
    """P1: for any out-of-range or non-numeric value, ai_retry_backoff == 2.0."""
    s = AppSettings(AI_RETRY_BACKOFF=v, **_ENV_NONE)
    assert s.ai_retry_backoff == pytest.approx(2.0)


def _is_numeric(s: str) -> bool:
    try:
        float(s)
        return True
    except (ValueError, TypeError):
        return False
