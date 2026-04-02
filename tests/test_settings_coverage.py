"""Additional tests for models/settings.py — covers validators and properties."""
import pytest

from src.models.settings import AppSettings


class TestAppSettingsValidators:
    """Tests for field validators — covers lines 109-199."""

    def test_invalid_rate_limit_falls_back_to_default(self):
        s = AppSettings(RATE_LIMIT="invalid-format", _env_file=None)
        assert s.rate_limit == "100/minute"

    def test_none_rate_limit_falls_back_to_default(self):
        s = AppSettings(RATE_LIMIT=None, _env_file=None)
        assert s.rate_limit == "100/minute"

    def test_valid_rate_limit_per_second(self):
        s = AppSettings(RATE_LIMIT="10/second", _env_file=None)
        assert s.rate_limit == "10/second"

    def test_valid_rate_limit_per_hour(self):
        s = AppSettings(RATE_LIMIT="500/hour", _env_file=None)
        assert s.rate_limit == "500/hour"

    def test_invalid_log_level_falls_back(self):
        s = AppSettings(LOG_LEVEL="VERBOSE", _env_file=None)
        assert s.log_level == "INFO"

    def test_none_log_level_falls_back(self):
        s = AppSettings(LOG_LEVEL=None, _env_file=None)
        assert s.log_level == "INFO"

    def test_valid_log_level_debug(self):
        s = AppSettings(LOG_LEVEL="debug", _env_file=None)
        assert s.log_level == "DEBUG"

    def test_invalid_log_format_falls_back(self):
        s = AppSettings(LOG_FORMAT="xml", _env_file=None)
        assert s.log_format == "text"

    def test_none_log_format_falls_back(self):
        s = AppSettings(LOG_FORMAT=None, _env_file=None)
        assert s.log_format == "text"

    def test_valid_log_format_json(self):
        s = AppSettings(LOG_FORMAT="json", _env_file=None)
        assert s.log_format == "json"


class TestAppSettingsProperties:
    """Tests for use_* properties — covers lines 155-199."""

    def test_use_gigachat_false_when_not_configured(self):
        s = AppSettings(
            GIGACHAT_CLIENT_ID=None,
            GIGACHAT_CLIENT_SECRET=None,
            _env_file=None,
        )
        assert s.use_gigachat is False

    def test_use_gigachat_false_with_placeholder_values(self):
        s = AppSettings(
            GIGACHAT_CLIENT_ID="your-client-id",
            GIGACHAT_CLIENT_SECRET="your-client-secret",
            _env_file=None
        )
        assert s.use_gigachat is False

    def test_use_gigachat_true_with_real_values(self):
        s = AppSettings(
            GIGACHAT_CLIENT_ID="real-client-id",
            GIGACHAT_CLIENT_SECRET="real-client-secret",
            _env_file=None
        )
        assert s.use_gigachat is True

    def test_use_qwen_false_when_not_configured(self):
        s = AppSettings(QWEN_API_KEY=None, QWEN_API_URL=None, _env_file=None)
        assert s.use_qwen is False

    def test_use_qwen_false_with_empty_url_from_env_style_input(self):
        s = AppSettings(QWEN_API_KEY="real-key", QWEN_API_URL="", _env_file=None)
        assert s.qwen_api_url is None
        assert s.use_qwen is False

    def test_use_qwen_false_with_placeholder_key(self):
        s = AppSettings(
            QWEN_API_KEY="your-api-key",
            QWEN_API_URL="https://api.qwen.ai/v1",
            _env_file=None
        )
        assert s.use_qwen is False

    def test_use_qwen_true_with_real_values(self):
        s = AppSettings(
            QWEN_API_KEY="real-key",
            QWEN_API_URL="https://real.api.com/v1",
            _env_file=None
        )
        assert s.use_qwen is True

    def test_use_local_llm_true_when_url_set(self):
        s = AppSettings(LLM_URL="http://localhost:11434/api/generate", _env_file=None)
        assert s.use_local_llm is True

    def test_use_huggingface_false_when_no_token(self):
        s = AppSettings(HF_TOKEN=None, _env_file=None)
        # hf_token explicitly set to None
        assert s.use_huggingface is False

    def test_use_huggingface_false_with_placeholder_token(self):
        s = AppSettings(HF_TOKEN="your-huggingface-token-here", _env_file=None)
        assert s.use_huggingface is False

    def test_use_huggingface_false_with_your_prefix(self):
        s = AppSettings(HF_TOKEN="your-custom-token", _env_file=None)
        assert s.use_huggingface is False

    def test_use_huggingface_true_with_real_token(self):
        s = AppSettings(HF_TOKEN="hf_realtoken123456", _env_file=None)
        assert s.use_huggingface is True
