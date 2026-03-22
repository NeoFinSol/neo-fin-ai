from pathlib import Path
import logging

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parents[2]
ENV_FILE = BASE_DIR / ".env"


class AppSettings(BaseSettings):
    qwen_api_key: str | None = Field(
        None,
        alias="QWEN_API_KEY",
        description="API key for Qwen service"
    )
    qwen_api_url: str | None = Field(
        None,
        alias="QWEN_API_URL",
        description="URL for Qwen API service"
    )

    model_config = SettingsConfigDict(env_file=str(ENV_FILE), extra="ignore")

    @field_validator("qwen_api_url", mode="before")
    @classmethod
    def validate_qwen_url(cls, v: str | None) -> str | None:
        """Validate Qwen API URL if provided."""
        if v is None:
            return None
        if not isinstance(v, str):
            raise ValueError("URL must be a string")
        if not (v.startswith("http://") or v.startswith("https://")):
            raise ValueError("URL must start with http:// or https://")
        return v


try:
    app_settings = AppSettings()
except ValueError as e:
    logging.warning(f"Settings validation warning: {e}. Some features may be disabled.")
    app_settings = AppSettings(_case_sensitive=False)
