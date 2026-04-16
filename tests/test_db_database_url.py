"""
Tests for _resolve_database_url() type contract guard (F2).

Unit tests: CI=1 paths, TESTING=1 paths.
PBT: Hypothesis property — CI=1 without URL always raises RuntimeError.
"""

import os
from unittest.mock import patch

import pytest
from hypothesis import given, settings as h_settings
from hypothesis import strategies as st

from src.db.database import _DB_TEST_URL_DEFAULT, _resolve_database_url


def _clean_env(**overrides):
    """Return a patched environment with DATABASE_URL and TEST_DATABASE_URL removed."""
    base = {k: v for k, v in os.environ.items() if k not in ("DATABASE_URL", "TEST_DATABASE_URL")}
    base.update(overrides)
    return base


class TestResolveDatabaseUrlCIMode:
    """CI=1 paths."""

    def test_ci_no_url_raises_runtime_error(self):
        env = _clean_env(CI="1", TESTING="0")
        with patch.dict(os.environ, env, clear=True), \
             patch("src.db.database.DATABASE_URL", None):
            with pytest.raises(RuntimeError, match="DATABASE_URL is not set"):
                _resolve_database_url()

    def test_ci_with_database_url_returns_str(self):
        url = "postgresql+asyncpg://user:pass@localhost/db"
        env = _clean_env(CI="1", TESTING="0", DATABASE_URL=url)
        with patch.dict(os.environ, env, clear=True), \
             patch("src.db.database.DATABASE_URL", url):
            result = _resolve_database_url()
        assert result == url
        assert isinstance(result, str)

    def test_ci_with_test_database_url_but_no_database_url_raises(self):
        # CI=1, TESTING=0 — TEST_DATABASE_URL is only used when TESTING=1
        env = _clean_env(CI="1", TESTING="0", TEST_DATABASE_URL="postgresql+asyncpg://t/test")
        with patch.dict(os.environ, env, clear=True), \
             patch("src.db.database.DATABASE_URL", None):
            with pytest.raises(RuntimeError, match="DATABASE_URL is not set"):
                _resolve_database_url()


class TestResolveDatabaseUrlTestingMode:
    """TESTING=1 paths."""

    def test_testing_with_test_database_url_returns_test_url(self):
        test_url = "postgresql+asyncpg://user:pass@localhost/test_db"
        env = _clean_env(TESTING="1", CI="0", TEST_DATABASE_URL=test_url)
        with patch.dict(os.environ, env, clear=True), \
             patch("src.db.database.DATABASE_URL", None):
            result = _resolve_database_url()
        assert result == test_url

    def test_testing_without_any_url_returns_default(self):
        env = _clean_env(TESTING="1", CI="0")
        with patch.dict(os.environ, env, clear=True), \
             patch("src.db.database.DATABASE_URL", None):
            result = _resolve_database_url()
        assert result == _DB_TEST_URL_DEFAULT
        assert isinstance(result, str)

    def test_testing_with_database_url_but_no_test_url_returns_database_url(self):
        url = "postgresql+asyncpg://user:pass@localhost/db"
        env = _clean_env(TESTING="1", CI="0", DATABASE_URL=url)
        with patch.dict(os.environ, env, clear=True), \
             patch("src.db.database.DATABASE_URL", url):
            result = _resolve_database_url()
        # No TEST_DATABASE_URL → falls through to DATABASE_URL
        assert result == url


class TestResolveDatabaseUrlNeverReturnsNone:
    """The function must never return None — it either returns str or raises."""

    def test_return_value_is_always_str_when_url_present(self):
        url = "postgresql+asyncpg://u:p@h/db"
        env = _clean_env(CI="1", TESTING="0", DATABASE_URL=url)
        with patch.dict(os.environ, env, clear=True), \
             patch("src.db.database.DATABASE_URL", url):
            result = _resolve_database_url()
        assert result is not None
        assert isinstance(result, str)


# ---------------------------------------------------------------------------
# PBT — Hypothesis property test (3.5)
# ---------------------------------------------------------------------------


@given(
    ci=st.just("1"),
    testing=st.just("0"),
)
@h_settings(max_examples=20)
def test_resolve_database_url_ci_no_url_always_raises(ci, testing):
    """P2: CI=1, no DATABASE_URL → always RuntimeError, never returns None."""
    env = _clean_env(CI=ci, TESTING=testing)
    with patch.dict(os.environ, env, clear=True), \
         patch("src.db.database.DATABASE_URL", None):
        with pytest.raises(RuntimeError, match="DATABASE_URL is not set"):
            _resolve_database_url()
