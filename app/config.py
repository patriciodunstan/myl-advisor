"""Configuration using pydantic-settings."""
from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )

    # App
    app_name: str = "MyL Advisor - AI Assistant"
    debug: bool = False
    api_v1_prefix: str = "/api/v1"

    # Database (shared with myl-database)
    database_url: str = "postgresql://localhost/myl_database"

    # Z.ai LLM configuration
    zai_api_key: str = "test_key"
    zai_api_base: str = "https://open.bigmodel.cn/api/paas/v4"
    zai_model: str = "glm-4.7-flash"

    # Rate limiting (LLM calls)
    llm_rate_limit_seconds: float = 2.0

    # Cache TTL (24 hours)
    cache_ttl_hours: int = 24

    # Logging
    log_level: str = "INFO"


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
