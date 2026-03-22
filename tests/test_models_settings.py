"""Tests for models/settings module."""
import pytest
from pydantic import ValidationError

from src.models.settings import AppSettings, app_settings


class TestAppSettings:
    """Tests for AppSettings class."""

    def test_default_settings_no_env(self):
        """Test default settings when no env vars provided."""
        settings = AppSettings()
        
        assert settings.qwen_api_key is None
        assert settings.qwen_api_url is None

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
