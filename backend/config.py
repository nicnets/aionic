from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache


class Settings(BaseSettings):
    """
    Infrastructure-only config loaded from .env.
    Application secrets (API keys, intervals, etc.) are managed in the
    admin panel and stored in the system_config table.
    """
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Database — must come from env, can't bootstrap from the DB itself
    database_url: str = "postgresql+asyncpg://aionic:aionic@localhost:5432/aionic"

    # CORS — infrastructure concern, not application config
    cors_origins: str = "http://localhost:3001,http://localhost:3000"

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
