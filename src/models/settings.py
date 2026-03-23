from pathlib import Path
import logging
import re

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parents[2]
ENV_FILE = BASE_DIR / ".env"


class AppSettings(BaseSettings):
    # Qwen AI settings (deprecated, use GigaChat instead)
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

    # GigaChat AI settings
    gigachat_client_id: str | None = Field(
        None,
        alias="GIGACHAT_CLIENT_ID",
        description="GigaChat Client ID"
    )
    gigachat_client_secret: str | None = Field(
        None,
        alias="GIGACHAT_CLIENT_SECRET",
        description="GigaChat Client Secret"
    )
    gigachat_auth_url: str | None = Field(
        "https://ngw.devices.sberbank.ru:9443/api/v2/oauth",
        alias="GIGACHAT_AUTH_URL",
        description="GigaChat OAuth authentication URL"
    )
    gigachat_chat_url: str | None = Field(
        "https://gigachat.devices.sberbank.ru/api/v1/chat/completions",
        alias="GIGACHAT_CHAT_URL",
        description="GigaChat chat completions API URL"
    )

    # Local LLM settings (Ollama)
    llm_url: str | None = Field(
        "http://localhost:11434/api/generate",
        alias="LLM_URL",
        description="Local LLM (Ollama) URL"
    )
    llm_model: str | None = Field(
        "llama3",
        alias="LLM_MODEL",
        description="Local LLM model name"
    )

    # Rate limiting settings
    rate_limit: str = Field(
        "100/minute",
        alias="RATE_LIMIT",
        description="Rate limit in format <count>/<period> (e.g., 100/minute)"
    )

    # Logging settings
    log_level: str = Field(
        "INFO",
        alias="LOG_LEVEL",
        description="Logging level: DEBUG, INFO, WARNING, ERROR, CRITICAL"
    )
    log_format: str = Field(
        "text",
        alias="LOG_FORMAT",
        description="Logging format: json or text"
    )

    model_config = SettingsConfigDict(env_file=str(ENV_FILE), extra="ignore")

    @field_validator("qwen_api_url", "gigachat_auth_url", "gigachat_chat_url", "llm_url", mode="before")
    @classmethod
    def validate_urls(cls, v: str | None) -> str | None:
        """Validate URLs if provided."""
        if v is None:
            return None
        if not isinstance(v, str):
            raise ValueError("URL must be a string")
        if not (v.startswith("http://") or v.startswith("https://")):
            raise ValueError("URL must start with http:// or https://")
        return v

    @field_validator("rate_limit", mode="before")
    @classmethod
    def validate_rate_limit(cls, v: str | None) -> str:
        """Validate rate limit format."""
        if v is None:
            return "100/minute"
        # Validate format: <count>/<period>
        pattern = r"^\d+/(second|minute|hour|day)$"
        if not re.match(pattern, v):
            logging.warning(f"Invalid rate limit format '{v}'. Using default '100/minute'")
            return "100/minute"
        return v

    @field_validator("log_level", mode="before")
    @classmethod
    def validate_log_level(cls, v: str | None) -> str:
        """Validate log level."""
        if v is None:
            return "INFO"
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        v_upper = v.upper()
        if v_upper not in valid_levels:
            logging.warning(f"Invalid log level '{v}'. Using default 'INFO'")
            return "INFO"
        return v_upper

    @field_validator("log_format", mode="before")
    @classmethod
    def validate_log_format(cls, v: str | None) -> str:
        """Validate log format."""
        if v is None:
            return "text"
        valid_formats = ["json", "text"]
        v_lower = v.lower()
        if v_lower not in valid_formats:
            logging.warning(f"Invalid log format '{v}'. Using default 'text'")
            return "text"
        return v_lower

    @model_validator(mode="after")
    def validate_all(self) -> "AppSettings":
        """Final validation after all fields are set."""
        # Additional cross-field validation can be added here
        return self

    @property
    def use_gigachat(self) -> bool:
        """Check if GigaChat is configured."""
        return bool(self.gigachat_client_id and self.gigachat_client_secret)

    @property
    def use_qwen(self) -> bool:
        """Check if Qwen is configured."""
        return bool(self.qwen_api_key and self.qwen_api_url)

    @property
    def use_local_llm(self) -> bool:
        """Check if local LLM (Ollama) is configured."""
        return bool(self.llm_url)


try:
    app_settings = AppSettings()
except ValueError as e:
    logging.warning(f"Settings validation warning: {e}. Some features may be disabled.")
    app_settings = AppSettings(_case_sensitive=False)
