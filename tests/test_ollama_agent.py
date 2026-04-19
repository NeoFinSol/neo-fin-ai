"""Tests for src/core/ollama_agent.py — F3, F4, F8 audit findings."""

import src.core.ollama_agent as ollama_module
from src.models.settings import app_settings
from src.utils.logging_config import ContextAdapter


class TestOllamaAgentF3StaleModelRemoved:
    """F3 — self.model must be None after construction (stale attr removed)."""

    def test_model_is_none_after_init(self):
        agent = ollama_module.OllamaAgent()
        assert agent.model is None

    def test_model_is_none_on_singleton(self):
        # The module-level singleton must also have model=None
        assert ollama_module.ollama_agent.model is None


class TestOllamaAgentF4TimeoutFromSettings:
    """F4 — singleton must use app_settings.ai_timeout, not hardcoded 120."""

    def test_singleton_timeout_matches_app_settings(self):
        assert ollama_module.ollama_agent.timeout == app_settings.ai_timeout

    def test_custom_timeout_respected(self):
        agent = ollama_module.OllamaAgent(timeout=300)
        assert agent.timeout == 300

    def test_effective_model_still_reads_settings_dynamically(self):
        agent = ollama_module.OllamaAgent()
        # _effective_model() must read app_settings, not self.model
        expected = app_settings.llm_model or "llama3"
        assert agent._effective_model() == expected


class TestOllamaAgentF8GetLogger:
    """F8 — module logger must be a ContextAdapter (project-standard get_logger)."""

    def test_logger_is_context_adapter(self):
        assert isinstance(ollama_module.logger, ContextAdapter)
