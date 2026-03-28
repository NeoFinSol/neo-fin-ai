from pathlib import Path
import logging
import os
import re

from dotenv import load_dotenv
from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parents[2]
ENV_FILE = BASE_DIR / ".env"

# Explicitly load .env file into os.environ for other modules that use os.getenv()
if ENV_FILE.exists():
    load_dotenv(str(ENV_FILE))


class AppSettings(BaseSettings):
    # Database
    database_url: str | None = Field(
        None, alias="DATABASE_URL", description="PostgreSQL connection string"
    )
    db_pool_size: int = Field(5, alias="DB_POOL_SIZE")
    db_max_overflow: int = Field(10, alias="DB_MAX_OVERFLOW")
    db_pool_timeout: int = Field(30, alias="DB_POOL_TIMEOUT")
    db_pool_recycle: int = Field(3600, alias="DB_POOL_RECYCLE")
    db_pool_pre_ping: bool = Field(True, alias="DB_POOL_PRE_PING")
    cleanup_batch_limit: int = Field(100, alias="CLEANUP_BATCH_LIMIT")
    analysis_cleanup_stale_hours: int = Field(48, alias="ANALYSIS_CLEANUP_STALE_HOURS")
    multi_session_stale_hours: int = Field(24, alias="MULTI_SESSION_STALE_HOURS")

    # Security
    api_key: str | None = Field(
        None, alias="API_KEY", description="API key for authentication"
    )
    dev_mode: bool = Field(
        False, alias="DEV_MODE", description="Development mode (disables auth)"
    )
    # Qwen AI settings (deprecated, use GigaChat instead)
    qwen_api_key: str | None = Field(
        None, alias="QWEN_API_KEY", description="API key for Qwen service"
    )
    qwen_api_url: str | None = Field(
        None, alias="QWEN_API_URL", description="URL for Qwen API service"
    )

    # GigaChat AI settings
    gigachat_client_id: str | None = Field(
        None, alias="GIGACHAT_CLIENT_ID", description="GigaChat Client ID"
    )
    gigachat_client_secret: str | None = Field(
        None, alias="GIGACHAT_CLIENT_SECRET", description="GigaChat Client Secret"
    )
    gigachat_auth_url: str | None = Field(
        "https://ngw.devices.sberbank.ru:9443/api/v2/oauth",
        alias="GIGACHAT_AUTH_URL",
        description="GigaChat OAuth authentication URL",
    )
    gigachat_chat_url: str | None = Field(
        "https://gigachat.devices.sberbank.ru/api/v1/chat/completions",
        alias="GIGACHAT_CHAT_URL",
        description="GigaChat chat completions API URL",
    )

    # Local LLM settings (Ollama)
    llm_url: str | None = Field(
        "http://localhost:11434/api/generate",
        alias="LLM_URL",
        description="Local LLM (Ollama) URL",
    )
    llm_model: str | None = Field(
        "llama3", alias="LLM_MODEL", description="Local LLM model name"
    )

    # Hugging Face settings
    hf_token: str | None = Field(
        None, alias="HF_TOKEN", description="Hugging Face API token"
    )
    hf_model: str | None = Field(
        "Qwen/Qwen3.5-9B-Instruct",
        alias="HF_MODEL",
        description="Hugging Face model name",
    )

    # Rate limiting settings
    rate_limit: str = Field(
        "100/minute",
        alias="RATE_LIMIT",
        description="Rate limit in format <count>/<period> (e.g., 100/minute)",
    )

    # Confidence threshold for extraction filtering
    confidence_threshold: float = Field(
        0.5,
        alias="CONFIDENCE_THRESHOLD",
        description="Minimum confidence score to include an extracted metric [0.0–1.0]",
    )

    # LLM Extraction settings
    llm_extraction_enabled: bool = Field(
        False,
        alias="LLM_EXTRACTION_ENABLED",
        description="Enable LLM-based financial metric extraction (experimental)",
    )
    llm_chunk_size: int = Field(
        12_000,
        alias="LLM_CHUNK_SIZE",
        description="Max characters per LLM request chunk [1000–50000]",
    )
    llm_max_chunks: int = Field(
        5,
        alias="LLM_MAX_CHUNKS",
        description="Max number of text chunks to process per PDF [1–20]",
    )
    llm_token_budget: int = Field(
        50_000,
        alias="LLM_TOKEN_BUDGET",
        description="Max total characters to process per PDF (≈ tokens × 4) [1000–200000]",
    )

    # Logging settings
    log_level: str = Field(
        "INFO",
        alias="LOG_LEVEL",
        description="Logging level: DEBUG, INFO, WARNING, ERROR, CRITICAL",
    )
    log_format: str = Field(
        "text", alias="LOG_FORMAT", description="Logging format: json or text"
    )

    model_config = SettingsConfigDict(env_file=str(ENV_FILE), extra="ignore")

    @field_validator(
        "qwen_api_url",
        "gigachat_auth_url",
        "gigachat_chat_url",
        "llm_url",
        mode="before",
    )
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

    @field_validator("confidence_threshold", mode="before")
    @classmethod
    def validate_confidence_threshold(cls, v: str | float | None) -> float:
        """Validate confidence threshold; fall back to 0.5 on invalid input."""
        if v is None:
            return 0.5
        try:
            value = float(v)
        except (TypeError, ValueError):
            logging.warning("Invalid CONFIDENCE_THRESHOLD=%r. Using default 0.5", v)
            return 0.5
        if not (0.0 <= value <= 1.0):
            logging.warning(
                "CONFIDENCE_THRESHOLD=%s out of [0.0, 1.0]. Using default 0.5", value
            )
            return 0.5
        return value

    @field_validator("llm_chunk_size", mode="before")
    @classmethod
    def validate_llm_chunk_size(cls, v: int | str | None) -> int:
        """Validate LLM chunk size; fall back to default on invalid input."""
        default = 12_000
        if v is None:
            return default
        try:
            value = int(v)
        except (TypeError, ValueError):
            logging.warning("Invalid LLM_CHUNK_SIZE=%r. Using default %d", v, default)
            return default
        if not (1_000 <= value <= 50_000):
            logging.warning(
                "LLM_CHUNK_SIZE=%d out of [1000, 50000]. Using default %d", value, default
            )
            return default
        return value

    @field_validator("llm_max_chunks", mode="before")
    @classmethod
    def validate_llm_max_chunks(cls, v: int | str | None) -> int:
        """Validate LLM max chunks; fall back to default on invalid input."""
        default = 5
        if v is None:
            return default
        try:
            value = int(v)
        except (TypeError, ValueError):
            logging.warning("Invalid LLM_MAX_CHUNKS=%r. Using default %d", v, default)
            return default
        if not (1 <= value <= 20):
            logging.warning(
                "LLM_MAX_CHUNKS=%d out of [1, 20]. Using default %d", value, default
            )
            return default
        return value

    @field_validator("llm_token_budget", mode="before")
    @classmethod
    def validate_llm_token_budget(cls, v: int | str | None) -> int:
        """Validate LLM token budget; fall back to default on invalid input."""
        default = 50_000
        if v is None:
            return default
        try:
            value = int(v)
        except (TypeError, ValueError):
            logging.warning("Invalid LLM_TOKEN_BUDGET=%r. Using default %d", v, default)
            return default
        if not (1_000 <= value <= 200_000):
            logging.warning(
                "LLM_TOKEN_BUDGET=%d out of [1000, 200000]. Using default %d", value, default
            )
            return default
        return value

    @field_validator("rate_limit", mode="before")
    @classmethod
    def validate_rate_limit(cls, v: str | None) -> str:
        """Validate rate limit format."""
        if v is None:
            return "100/minute"
        # Validate format: <count>/<period>
        pattern = r"^\d+/(second|minute|hour|day)$"
        if not re.match(pattern, v):
            logging.warning(
                f"Invalid rate limit format '{v}'. Using default '100/minute'"
            )
            return "100/minute"
        return v

    @field_validator(
        "cleanup_batch_limit",
        "analysis_cleanup_stale_hours",
        "multi_session_stale_hours",
        mode="before",
    )
    @classmethod
    def validate_positive_ints(cls, v: int | str | None, info) -> int:
        defaults = {
            "cleanup_batch_limit": 100,
            "analysis_cleanup_stale_hours": 48,
            "multi_session_stale_hours": 24,
        }
        default = defaults[info.field_name]
        if v is None:
            return default
        try:
            value = int(v)
        except (TypeError, ValueError):
            logging.warning("Invalid %s=%r. Using default %d", info.field_name, v, default)
            return default
        if value <= 0:
            logging.warning("%s=%r must be positive. Using default %d", info.field_name, v, default)
            return default
        return value

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
        if not (self.gigachat_client_id and self.gigachat_client_secret):
            return False
        cid = self.gigachat_client_id.lower().strip()
        csec = self.gigachat_client_secret.lower().strip()
        if cid in ("your-client-id", "none", "") or csec in (
            "your-client-secret",
            "none",
            "",
        ):
            return False
        return True

    @property
    def use_qwen(self) -> bool:
        """Check if Qwen is configured."""
        if not (self.qwen_api_key and self.qwen_api_url):
            return False
        key = self.qwen_api_key.lower().strip()
        url = self.qwen_api_url.lower().strip()
        if key in ("your-api-key", "none", "") or url in ("https://api.qwen.ai/v1",):
            return False
        return True

    @property
    def use_local_llm(self) -> bool:
        """Check if local LLM (Ollama) is configured."""
        return bool(self.llm_url)

    @property
    def use_huggingface(self) -> bool:
        """Check if Hugging Face is configured."""
        if not self.hf_token:
            return False
        token = self.hf_token.lower().strip()
        if token in ("your-huggingface-token-here", "none", "") or token.startswith(
            "your-"
        ):
            return False
        return True


try:
    app_settings = AppSettings()
except ValueError as e:
    logging.warning(f"Settings validation warning: {e}. Some features may be disabled.")
    app_settings = AppSettings(_case_sensitive=False)
