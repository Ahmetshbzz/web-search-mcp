from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

_ENV_FILE = Path(__file__).resolve().parents[2] / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=_ENV_FILE,
        env_file_encoding="utf-8",
        extra="ignore",
    )

    brave_api_key: str = ""
    tavily_api_key: str = ""
    exa_api_key: str = ""
    x_bearer_token: str = ""
    searxng_base_url: str = ""
    search_mode: str = "parallel"  # "parallel" | "fallback" | "fast"
    cache_db_path: str = "data/cache.db"
    fetch_max_bytes: int = 10 * 1024 * 1024  # tek doküman için üst sınır (Lexa parity)

    max_results: int = 8
    max_provider_results: int = 20
    max_content_chars: int = 6000
    fetch_top_pages: int = 5
    cache_ttl_seconds: int = 300
    page_cache_ttl_seconds: int = 900

    search_timeout: float = 12.0
    provider_timeout: float = 14.0  # tek provider'ın hard limiti (parallel/fast modda)
    fetch_timeout: float = 8.0
    page_timeout: float = 15.0
    max_retries: int = 1

    user_agent: str = (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36"
    )


RECENCY_OPTIONS = frozenset({"day", "week", "month", "year"})


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    # .env her çağrıda yeniden parse edilmez; process ömrü boyunca tek instance.
    return Settings()
