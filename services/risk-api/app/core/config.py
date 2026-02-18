"""Application configuration loaded from environment variables."""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Upstream services
    market_engine_url: str = "http://localhost:8080"
    settlement_oracle_url: str = "http://localhost:8000"

    # LMSR defaults
    default_liquidity_b: float = 100.0
    notional_payout_usd: float = 10.0
    loading_factor: float = 0.10  # 10% over fair value for market-maker spread

    # NWS API
    nws_api_base: str = "https://api.weather.gov"
    nws_request_timeout: float = 5.0

    # Settlement rule defaults (matching settlement oracle config)
    min_stations: int = 1
    dispute_spread_ratio: float = 0.2
    settlement_rule_version: str = "v1.3"

    # Pricing
    pricing_model: str = "ensemble_baseline_v1"
    price_validity_minutes: int = 5

    # Settlement cron
    settlement_cron_interval_seconds: int = 30
    settlement_cron_enabled: bool = True
    settlement_lookback_minutes: int = 60

    # Webhooks
    webhook_timeout_seconds: float = 10.0
    webhook_max_retries: int = 3

    # Authentication
    admin_secret: str = "changeme-admin-secret"
    bootstrap_api_key: str | None = None

    # Rate limiting
    default_rate_limit: int = 60
    rate_limit_window_seconds: int = 60

    # H3
    h3_resolution: int = 7

    log_level: str = "INFO"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}


settings = Settings()
