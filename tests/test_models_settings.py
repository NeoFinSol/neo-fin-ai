"""Tests for models/settings module."""
from pathlib import Path
import pytest
from pydantic import ValidationError
from unittest.mock import patch, MagicMock

from src.models.settings import AppSettings, app_settings


class TestAppSettings:
    """Tests for AppSettings class."""

    def test_default_settings_no_env(self):
        """Test default settings when no env vars provided (env vars cleared)."""
        import os
        # Clear relevant env vars and bypass .env file reading
        env_keys = ["QWEN_API_KEY", "QWEN_API_URL"]
        saved = {k: os.environ.pop(k, None) for k in env_keys}
        try:
            # Pass _env_file=None to prevent reading .env file
            settings = AppSettings(_env_file=None)
            assert settings.qwen_api_key is None
            assert settings.qwen_api_url is None
        finally:
            for k, v in saved.items():
                if v is not None:
                    os.environ[k] = v

    def test_settings_with_qwen_api_key(self):
        """Test settings with QWEN_API_KEY."""
        settings = AppSettings(QWEN_API_KEY="test-key-123")
        
        assert settings.qwen_api_key == "test-key-123"

    def test_settings_with_qwen_api_url_http(self):
        """Test settings with HTTP URL."""
        settings = AppSettings(QWEN_API_URL="http://api.example.com/v1")
        
        assert settings.qwen_api_url == "http://api.example.com/v1"

    def test_settings_with_qwen_api_url_https(self):
        """Test settings with HTTPS URL."""
        settings = AppSettings(QWEN_API_URL="https://api.example.com/v1")
        
        assert settings.qwen_api_url == "https://api.example.com/v1"

    def test_settings_with_both_credentials(self):
        """Test settings with both API key and URL."""
        settings = AppSettings(
            QWEN_API_KEY="my-secret-key",
            QWEN_API_URL="https://api.qwen.ai/v1"
        )
        
        assert settings.qwen_api_key == "my-secret-key"
        assert settings.qwen_api_url == "https://api.qwen.ai/v1"

    def test_validate_url_invalid_no_protocol(self):
        """Test validation rejects URL without protocol."""
        with pytest.raises(ValidationError) as exc_info:
            AppSettings(QWEN_API_URL="api.example.com/v1")
        
        assert "http://" in str(exc_info.value) or "https://" in str(exc_info.value)

    def test_validate_url_invalid_ftp(self):
        """Test validation rejects FTP protocol."""
        with pytest.raises(ValidationError) as exc_info:
            AppSettings(QWEN_API_URL="ftp://files.example.com/api")
        
        assert "http://" in str(exc_info.value) or "https://" in str(exc_info.value)

    def test_validate_url_none_allowed(self):
        """Test that None URL passes validation."""
        settings = AppSettings(QWEN_API_URL=None)
        assert settings.qwen_api_url is None

    def test_validate_url_wrong_type(self):
        """Test validation rejects non-string URL."""
        with pytest.raises(ValidationError) as exc_info:
            AppSettings(QWEN_API_URL=12345)
        
        assert "string" in str(exc_info.value).lower()

    def test_validate_url_empty_string(self):
        """Test validation of empty string URL."""
        # Empty string doesn't start with http/https, should fail
        with pytest.raises(ValidationError):
            AppSettings(QWEN_API_URL="")

    def test_model_config_extra_ignore(self):
        """Test that extra fields are ignored."""
        # Should not raise even with unknown field
        settings = AppSettings(
            QWEN_API_KEY="key",
            UNKNOWN_FIELD="should be ignored"
        )
        
        assert settings.qwen_api_key == "key"
        assert not hasattr(settings, 'unknown_field')

    def test_description_metadata(self):
        """Test field descriptions are set."""
        model_json = AppSettings.model_json_schema()
        
        assert 'QWEN_API_KEY' in str(model_json) or 'qwen_api_key' in str(model_json)
        assert 'API key' in str(model_json) or 'Qwen' in str(model_json)

    def test_cleanup_settings_defaults(self):
        """Cleanup settings should expose safe operational defaults."""
        settings = AppSettings(_env_file=None)

        assert settings.cleanup_batch_limit == 100
        assert settings.analysis_cleanup_stale_hours == 48
        assert settings.multi_session_stale_hours == 24
        assert settings.runtime_recovery_batch_limit == 100
        assert settings.analysis_runtime_stale_minutes == 60
        assert settings.multi_session_runtime_stale_minutes == 90

    def test_cleanup_settings_invalid_values_fallback(self):
        """Invalid cleanup values should fall back to safe defaults."""
        settings = AppSettings(
            _env_file=None,
            CLEANUP_BATCH_LIMIT="bad",
            ANALYSIS_CLEANUP_STALE_HOURS=0,
            MULTI_SESSION_STALE_HOURS="-1",
            RUNTIME_RECOVERY_BATCH_LIMIT="bad",
            ANALYSIS_RUNTIME_STALE_MINUTES=0,
            MULTI_SESSION_RUNTIME_STALE_MINUTES="-1",
        )

        assert settings.cleanup_batch_limit == 100
        assert settings.analysis_cleanup_stale_hours == 48
        assert settings.multi_session_stale_hours == 24
        assert settings.runtime_recovery_batch_limit == 100
        assert settings.analysis_runtime_stale_minutes == 60
        assert settings.multi_session_runtime_stale_minutes == 90

    def test_task_runtime_settings_defaults(self):
        """Persistent runtime settings should keep safe local defaults."""
        settings = AppSettings(_env_file=None)

        assert settings.task_runtime == "background"
        assert settings.task_storage_dir is None
        assert settings.task_queue_broker_url is None
        assert settings.task_queue_result_backend is None
        assert settings.task_events_redis_url is None
        assert settings.task_queue_name == "neofin"
        assert settings.task_queue_eager is False

    def test_task_runtime_accepts_shared_storage_dir(self):
        settings = AppSettings(_env_file=None, TASK_STORAGE_DIR="/shared/task-files")
        assert settings.task_storage_dir == "/shared/task-files"

    def test_task_runtime_invalid_value_falls_back_to_background(self):
        """Invalid runtime values should not break local development."""
        settings = AppSettings(_env_file=None, TASK_RUNTIME="invalid-runtime")
        assert settings.task_runtime == "background"

    def test_task_runtime_urls_validate(self):
        """Redis/Celery URLs should use the same http(s)/redis URL validator path."""
        settings = AppSettings(
            _env_file=None,
            TASK_QUEUE_BROKER_URL="redis://localhost:6379/0",
            TASK_QUEUE_RESULT_BACKEND="redis://localhost:6379/1",
            TASK_EVENTS_REDIS_URL="redis://localhost:6379/2",
        )

        assert settings.task_queue_broker_url == "redis://localhost:6379/0"
        assert settings.task_queue_result_backend == "redis://localhost:6379/1"
        assert settings.task_events_redis_url == "redis://localhost:6379/2"

    def test_scoring_profile_defaults_to_auto(self):
        settings = AppSettings(_env_file=None)
        assert settings.scoring_profile == "auto"

    def test_scoring_profile_accepts_retail_demo(self):
        settings = AppSettings(_env_file=None, SCORING_PROFILE="retail_demo")
        assert settings.scoring_profile == "retail_demo"

    def test_scoring_profile_invalid_value_falls_back_to_auto(self):
        settings = AppSettings(_env_file=None, SCORING_PROFILE="invalid-profile")
        assert settings.scoring_profile == "auto"


class TestGlobalAppSettings:
    """Tests for global app_settings instance."""

    def test_global_settings_exists(self):
        """Test that global settings instance exists."""
        assert app_settings is not None
        assert isinstance(app_settings, AppSettings)

    def test_global_settings_has_attributes(self):
        """Test global settings has expected attributes."""
        assert hasattr(app_settings, 'qwen_api_key')
        assert hasattr(app_settings, 'qwen_api_url')

    def test_global_settings_values(self):
        """Test global settings values (may be None if no .env)."""
        # Values depend on .env file presence, but should not crash
        assert app_settings.qwen_api_key is None or isinstance(app_settings.qwen_api_key, str)
        assert app_settings.qwen_api_url is None or isinstance(app_settings.qwen_api_url, str)


class TestSettingsExceptionHandling:
    """Tests for settings exception handling."""

    def test_exception_handler_code_exists(self):
        """Test that exception handler code path exists in module."""
        # The try/except block at module level handles ValueError
        # This is difficult to test directly without reloading the module
        # Verify the fallback app_settings is created properly
        from src.models import settings
        
        # Should have app_settings defined
        assert hasattr(settings, 'app_settings')
        assert settings.app_settings is not None
