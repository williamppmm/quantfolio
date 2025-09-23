from __future__ import annotations

from functools import lru_cache
from typing import List

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

DEFAULT_ALLOWED_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    env: str = Field(default="dev", alias="ENV")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    database_url: str = Field(alias="DATABASE_URL")
    allowed_origins_raw: str = Field(
        default=",".join(DEFAULT_ALLOWED_ORIGINS),
        alias="ALLOWED_ORIGINS",
    )
    scheduler_enabled: bool = Field(default=False, alias="SCHEDULER_ENABLED")
    watchlist_raw: str = Field(default="", alias="WATCHLIST")

    @property
    def allowed_origins(self) -> List[str]:
        items = [item.strip() for item in self.allowed_origins_raw.split(",") if item.strip()]
        return items or DEFAULT_ALLOWED_ORIGINS.copy()

    @property
    def watchlist(self) -> List[str]:
        if not self.watchlist_raw:
            return []
        return [item.strip().upper() for item in self.watchlist_raw.split(",") if item.strip()]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    settings = Settings()
    if not settings.database_url:
        raise ValueError("DATABASE_URL is required. Provide it via environment or .env file.")
    return settings
