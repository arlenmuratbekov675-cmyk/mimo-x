"""Application configuration loaded from environment / .env file."""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "MiMo X"
    environment: str = "development"
    database_url: str = "sqlite:///./mimo_x.db"

    # API keys (kept on the server, never in the browser). Unused at Step 0.
    twelvedata_api_key: str = ""
    fred_api_key: str = ""


settings = Settings()
