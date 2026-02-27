import os
from pathlib import Path

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Database
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/logistics_news"

    # Application
    log_level: str = "INFO"
    api_host: str = "0.0.0.0"
    api_port: int = 8000

    # Fetch settings
    rss_fetch_interval_minutes: int = 30
    default_fetch_timeout_seconds: int = 30
    max_articles_per_fetch: int = 50

    # Paths
    base_dir: Path = Path(__file__).resolve().parent.parent
    sources_yaml_path: Path = Path(__file__).resolve().parent / "sources.yaml"

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
    }


settings = Settings()
