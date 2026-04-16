"""
Tests for Commit 4 audit findings (F6, F7, F9).

F7: _check_state_transition dead method removed from CircuitBreaker
F6: dead except CircuitBreakerOpenError removed from AIService.invoke()
F9: CircuitBreakerOpenError now accepts optional details parameter
PBT: Hypothesis property for CircuitBreakerOpenError constructor invariant
"""

import inspect

import pytest
from hypothesis import given, settings as h_settings
from hypothesis import strategies as st

from src.exceptions import BaseAppError, CircuitBreakerOpenError
from src.utils.circuit_breaker import CircuitBreaker


# ---------------------------------------------------------------------------
# F7 — dead _check_state_transition removed
# ---------------------------------------------------------------------------


class TestCircuitBreakerDeadMethodRemoved:
    def test_check_state_transition_locked_does_not_exist(self):
        """F7: _check_state_transition (locked variant) must be gone."""
        breaker = CircuitBreaker(name="test")
        assert not hasattr(breaker, "_check_state_transition")

    def test_check_state_transition_unlocked_still_exists(self):
        """The unlocked variant used by properties must still be present."""
        breaker = CircuitBreaker(name="test")
        assert hasattr(breaker, "_check_state_transition_unlocked")
        assert callable(breaker._check_state_transition_unlocked)

    def test_state_property_still_works(self):
        """State machine properties must be unaffected by the removal."""
        from src.utils.circuit_breaker import CircuitState

        breaker = CircuitBreaker(name="test")
        assert breaker.state == CircuitState.CLOSED
        assert breaker.is_available is True


# ---------------------------------------------------------------------------
# F6 — dead except CircuitBreakerOpenError removed from ai_service
# ---------------------------------------------------------------------------


class TestAIServiceDeadCatchRemoved:
    def test_circuit_breaker_open_error_not_imported_in_ai_service(self):
        """F6: CircuitBreakerOpenError must not appear in ai_service imports."""
        import src.core.ai_service as ai_module

        assert not hasattr(ai_module, "CircuitBreakerOpenError"), (
            "CircuitBreakerOpenError should not be imported in ai_service after F6 fix"
        )

    def test_invoke_method_has_no_circuit_breaker_open_error_handler(self):
        """F6: invoke() source must not contain the dead except clause."""
        import src.core.ai_service as ai_module

        source = inspect.getsource(ai_module.AIService.invoke)
        assert "CircuitBreakerOpenError" not in source

    def test_timeout_error_still_caught(self):
        """F6: asyncio.TimeoutError handler must still be present."""
        import src.core.ai_service as ai_module

        source = inspect.getsource(ai_module.AIService.invoke)
        assert "asyncio.TimeoutError" in source

    def test_generic_exception_still_caught(self):
        """F6: generic Exception handler must still be present."""
        import src.core.ai_service as ai_module

        source = inspect.getsource(ai_module.AIService.invoke)
        assert "except Exception" in source


# ---------------------------------------------------------------------------
# F9 — CircuitBreakerOpenError accepts optional details
# ---------------------------------------------------------------------------


class TestCircuitBreakerOpenErrorDetails:
    def test_no_details_gives_empty_dict(self):
        """F9: backward-compatible call — details defaults to {}."""
        err = CircuitBreakerOpenError("svc", 30)
        assert err.details == {}

    def test_explicit_none_gives_empty_dict(self):
        err = CircuitBreakerOpenError("svc", 30, None)
        assert err.details == {}

    def test_details_dict_is_stored(self):
        err = CircuitBreakerOpenError("svc", 30, {"key": "value"})
        assert err.details == {"key": "value"}

    def test_is_base_app_error(self):
        err = CircuitBreakerOpenError("svc", 30)
        assert isinstance(err, BaseAppError)

    def test_code_is_circuit_breaker_open(self):
        err = CircuitBreakerOpenError("svc", 30)
        assert err.code == "CIRCUIT_BREAKER_OPEN"

    def test_service_name_and_retry_after_preserved(self):
        err = CircuitBreakerOpenError("my-service", 60, {"ctx": "x"})
        assert err.service_name == "my-service"
        assert err.retry_after == 60

    def test_message_contains_service_name_and_retry(self):
        err = CircuitBreakerOpenError("ai-svc", 45)
        assert "ai-svc" in err.message
        assert "45" in err.message

    def test_to_dict_includes_code_and_message(self):
        err = CircuitBreakerOpenError("svc", 10)
        d = err.to_dict()
        assert d["code"] == "CIRCUIT_BREAKER_OPEN"
        assert "svc" in d["message"]

    def test_to_dict_with_details_includes_details(self):
        err = CircuitBreakerOpenError("svc", 10, {"reason": "overload"})
        d = err.to_dict(include_details=True)
        assert d["details"] == {"reason": "overload"}


# ---------------------------------------------------------------------------
# PBT — Hypothesis property test (4.7)
# ---------------------------------------------------------------------------


@given(
    service_name=st.text(min_size=1, max_size=64),
    retry_after=st.integers(min_value=0, max_value=3600),
    details=st.one_of(
        st.none(),
        st.dictionaries(st.text(max_size=20), st.text(max_size=50)),
    ),
)
@h_settings(max_examples=100)
def test_circuit_breaker_open_error_invariant(service_name, retry_after, details):
    """P3: for any inputs, CircuitBreakerOpenError is always a valid BaseAppError."""
    err = CircuitBreakerOpenError(service_name, retry_after, details)
    assert isinstance(err, BaseAppError)
    assert err.code == "CIRCUIT_BREAKER_OPEN"
    assert err.service_name == service_name
    assert err.retry_after == retry_after
    # details=None must produce {} (BaseAppError default)
    expected_details = details if details is not None else {}
    assert err.details == expected_details
