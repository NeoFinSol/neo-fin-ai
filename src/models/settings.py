from pathlib import Path

from pydantic import AnyUrl, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parents[2]
ENV_FILE = BASE_DIR / ".env"


class AppSettings(BaseSettings):
    qwen_api_key: str | None = Field(
        None,
        alias="QWEN_API_KEY",
        description="API ключ для сервиса Qwen"
    )
    qwen_api_url: AnyUrl | None = Field(
        None,
        alias="QWEN_API_URL",
        description="URL API сервиса Qwen"
    )

    model_config = SettingsConfigDict(env_file=str(ENV_FILE), extra="ignore")


app_settings = AppSettings()
