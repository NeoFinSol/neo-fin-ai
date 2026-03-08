from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class AppSettings(BaseSettings):
	qwen_api_key: str = Field(None, alias="QWEN_API_KEY")
	qwen_api_url: str = Field(None, alias="QWEN_API_URL")

	model_config = SettingsConfigDict(env_file=".env", extra="ignore")


app_settings = AppSettings()
