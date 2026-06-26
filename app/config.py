"""Application configuration loaded from environment / .env file."""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "MiMo X"
    environment: str = "development"
    database_url: str = "sqlite:///./mimo_x.db"

    # API keys (kept on the server, never in the browser).
    twelvedata_api_key: str = ""
    fred_api_key: str = ""

    # Step 5: caching to avoid provider rate limits (TwelveData free ~8 req/min).
    cache_ttl_seconds: int = 300

    # Step 6: optional API auth. If set, callers must send  X-API-Key: <value>.
    # Empty string = auth disabled (open), so existing setups keep working.
    api_key: str = ""

    # Step 7: minimum forward-tested samples before confidence becomes a number.
    backtest_min_samples: int = 30
    backtest_horizon_hours: int = 24

    # Tradovate (real futures data). Empty = use ETF proxies instead.
    tradovate_username: str = ""
    tradovate_password: str = ""
    tradovate_app_id: str = "MiMoX"
    tradovate_app_version: str = "1.0"
    tradovate_cid: str = ""          # client id (from API access request)
    tradovate_sec: str = ""          # client secret
    tradovate_demo: bool = True      # demo (sim) vs live endpoint
    # Which feed to use for instruments: "auto" (tradovate if creds else proxy),
    # "tradovate", or "proxy".
    price_feed: str = "auto"


settings = Settings()
