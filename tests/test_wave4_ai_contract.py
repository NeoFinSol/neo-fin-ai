"""
Wave 4B — TEST-003: AI contract regression tests.

Verifies the unified error hierarchy and public configuration contract
across all AI agents and AIService.
"""

import pytest

from src.core.agent import Agent
from src.core.agent import ConfigurationError as AgentConfigError
from src.core.base_agent import AIAgentError, BaseAIAgent, ConfigurationError
from src.core.gigachat_agent import GigaChatAgent
from src.core.huggingface_agent import HuggingFaceAgent

# ---------------------------------------------------------------------------
# ARCH-003: single ConfigurationError identity
# ---------------------------------------------------------------------------


class TestConfigurationErrorIdentity:
    """ConfigurationError must be one class, not duplicates."""

    def test_agent_module_reexports_base_configuration_error(self):
        """agent.ConfigurationError must be the same class as base_agent.ConfigurationError."""
        assert AgentConfigError is ConfigurationError

    def test_configuration_error_is_ai_agent_error_subclass(self):
        assert issubclass(ConfigurationError, AIAgentError)

    def test_configuration_error_is_exception_subclass(self):
        assert issubclass(ConfigurationError, Exception)

    def test_gigachat_raises_canonical_configuration_error_on_empty_id(self):
        agent = GigaChatAgent()
        with pytest.raises(ConfigurationError):
            agent.set_config("", "secret")

    def test_huggingface_raises_canonical_configuration_error_on_empty_token(self):
        agent = HuggingFaceAgent()
        with pytest.raises(ConfigurationError):
            agent.set_config("")

    def test_qwen_raises_canonical_configuration_error_on_empty_token(self):
        agent = Agent()
        with pytest.raises(ConfigurationError):
            agent.set_config("", "https://api.example.com")


# ---------------------------------------------------------------------------
# ARCH-004: all agents use ConfigurationError, not ValueError
# ---------------------------------------------------------------------------


class TestNoValueErrorFromAgents:
    """Agents must not raise ValueError for configuration issues."""

    def test_gigachat_set_config_empty_id_is_not_value_error(self):
        agent = GigaChatAgent()
        with pytest.raises(ConfigurationError):
            agent.set_config("", "secret")
        # Ensure it is NOT a plain ValueError
        try:
            agent.set_config("", "secret")
        except ConfigurationError:
            pass  # correct
        except ValueError:
            pytest.fail("GigaChatAgent raised ValueError instead of ConfigurationError")

    def test_gigachat_ensure_configured_is_not_value_error(self):
        agent = GigaChatAgent()
        with pytest.raises(ConfigurationError):
            agent._ensure_configured()

    def test_huggingface_ensure_configured_is_not_value_error(self):
        agent = HuggingFaceAgent()
        with pytest.raises(ConfigurationError):
            agent._ensure_configured()

    def test_qwen_ensure_configured_is_not_value_error(self):
        agent = Agent()
        with pytest.raises(ConfigurationError):
            agent._ensure_configured()


# ---------------------------------------------------------------------------
# ARCH-005: public is_configured property, no ._configured access needed
# ---------------------------------------------------------------------------


class TestPublicIsConfiguredProperty:
    """BaseAIAgent must expose is_configured as a public property."""

    def test_base_agent_has_is_configured_property(self):
        assert isinstance(BaseAIAgent.is_configured, property)

    def test_gigachat_is_configured_false_before_set_config(self):
        agent = GigaChatAgent()
        assert agent.is_configured is False

    def test_gigachat_is_configured_true_after_set_config(self):
        agent = GigaChatAgent()
        agent.set_config("cid", "csec")
        assert agent.is_configured is True

    def test_huggingface_is_configured_false_before_set_config(self):
        agent = HuggingFaceAgent()
        assert agent.is_configured is False

    def test_huggingface_is_configured_true_after_set_config(self):
        agent = HuggingFaceAgent()
        agent.set_config("hf-token")
        assert agent.is_configured is True

    def test_qwen_is_configured_false_before_set_config(self):
        agent = Agent()
        assert agent.is_configured is False

    def test_qwen_is_configured_true_after_set_config(self):
        agent = Agent()
        agent.set_config("token", "https://api.example.com")
        assert agent.is_configured is True


# ---------------------------------------------------------------------------
# ARCH-007: unified configuration contract across providers
# ---------------------------------------------------------------------------


class TestUnifiedConfigurationContract:
    """All agents must follow the same set_config / _ensure_configured contract."""

    @pytest.mark.parametrize(
        "agent_cls, valid_args, invalid_args",
        [
            (GigaChatAgent, ("cid", "csec"), ("", "csec")),
            (HuggingFaceAgent, ("hf-token",), ("",)),
            (
                Agent,
                ("token", "https://api.example.com"),
                ("", "https://api.example.com"),
            ),
        ],
    )
    def test_set_config_valid_sets_is_configured(
        self, agent_cls, valid_args, invalid_args
    ):
        agent = agent_cls()
        agent.set_config(*valid_args)
        assert agent.is_configured is True

    @pytest.mark.parametrize(
        "agent_cls, invalid_args",
        [
            (GigaChatAgent, ("", "csec")),
            (HuggingFaceAgent, ("",)),
            (Agent, ("", "https://api.example.com")),
        ],
    )
    def test_set_config_invalid_raises_configuration_error(
        self, agent_cls, invalid_args
    ):
        agent = agent_cls()
        with pytest.raises(ConfigurationError):
            agent.set_config(*invalid_args)

    @pytest.mark.parametrize("agent_cls", [GigaChatAgent, HuggingFaceAgent, Agent])
    def test_ensure_configured_raises_when_not_configured(self, agent_cls):
        agent = agent_cls()
        with pytest.raises(ConfigurationError):
            agent._ensure_configured()

    @pytest.mark.parametrize("agent_cls", [GigaChatAgent, HuggingFaceAgent, Agent])
    def test_ensure_configured_does_not_raise_when_configured(self, agent_cls):
        agent = agent_cls()
        if agent_cls is GigaChatAgent:
            agent.set_config("cid", "csec")
        elif agent_cls is HuggingFaceAgent:
            agent.set_config("hf-token")
        else:
            agent.set_config("token", "https://api.example.com")
        agent._ensure_configured()  # must not raise
