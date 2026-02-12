"""Application configuration loaded from environment variables."""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://settler:settler@localhost:5432/contract_settler"
    sync_database_url: str = "postgresql://settler:settler@localhost:5432/contract_settler"

    # AWS / NOAA
    aws_region: str = "us-east-1"
    noaa_s3_bucket: str = "noaa-hrrr-bdp-pds"

    # ASOS observation source
    asos_base_url: str = "https://mesonet.agron.iastate.edu/cgi-bin/request/asos.py"

    # Settlement tuning
    settlement_hash_algorithm: str = "sha256"
    min_stations_for_settlement: int = 1
    disputed_threshold_ratio: float = 0.2  # 20% disagreement among stations → DISPUTED

    log_level: str = "INFO"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}


settings = Settings()
