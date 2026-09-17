from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    app_name: str = "auction-system"
    app_version: str = "0.1.0"
    environment: str = "development"
    database_url: str
    test_database_url: str | None = None
    backup_file: str = "backup.sql"
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

@lru_cache
def get_settings() -> Settings:
    return Settings()
