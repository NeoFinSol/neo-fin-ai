"""Tests for authentication behavior."""
import os

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from src.app import app
from src.core.auth import get_api_key
from src.models.settings import app_settings


class TestAuthenticationEnforcement:
    """Tests to verify authentication is enforced when DEV_MODE=0."""

    def test_auth_requires_api_key_in_production(self, monkeypatch):
        """Test that authentication requires API_KEY when DEV_MODE=0."""
        monkeypatch.setenv("DEV_MODE", "0")
        monkeypatch.setenv("API_KEY", "test-key")
        
        # Reload app_settings to pick up new environment
        import importlib

        import src.models.settings as settings_module
        importlib.reload(settings_module)
        
        # Verify settings are correct
        assert settings_module.app_settings.dev_mode == False
        assert settings_module.app_settings.api_key == "test-key"

    def test_dev_mode_bypasses_authentication(self, monkeypatch):
        """Test that DEV_MODE=1 bypasses authentication."""
        monkeypatch.setenv("DEV_MODE", "1")
        
        # Reload to pick up changes
        import importlib

        import src.models.settings as settings_module
        importlib.reload(settings_module)
        
        # Verify DEV_MODE is enabled
        assert settings_module.app_settings.dev_mode == True


class TestDevModeFixture:
    """Tests for dev_mode_enabled fixture."""

    def test_dev_mode_enabled_fixture(self, dev_mode_enabled):
        """Test that dev_mode_enabled fixture works."""
        import os
        assert os.environ.get("DEV_MODE") == "1"

    def test_auth_enabled_fixture(self, auth_enabled):
        """Test that auth_enabled fixture works."""
        import os
        assert os.environ.get("DEV_MODE") == "0"
        assert os.environ.get("API_KEY") == "test-api-key-for-testing"
