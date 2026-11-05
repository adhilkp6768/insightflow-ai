from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    environment: str = "development"
    database_url: str = "postgresql+psycopg://insightflow:insightflow@localhost:5432/insightflow"
    redis_url: str = ""
    jwt_secret: str = ""
    jwt_algorithm: str = "HS256"
    jwt_access_ttl_seconds: int = 900
    jwt_refresh_ttl_seconds: int = 60 * 60 * 24 * 7
    cors_origins: str = "http://localhost:5173"
    rate_limit_enabled: bool = True
    jobs_inline: bool = False
    log_level: str = "INFO"
    app_name: str = "InsightFlow AI"
    app_version: str = "0.1.0"
    data_dir: str = "data"
    max_upload_bytes: int = 100 * 1024 * 1024
    assistant_row_limit: int = 500
    assistant_timeout_ms: int = 5000
    insightflow_llm_api_key: str = ""
    insightflow_llm_base_url: str = "https://api.openai.com/v1"
    insightflow_llm_model: str = "gpt-4o-mini"

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    if len(settings.jwt_secret) < 32:
        raise RuntimeError("JWT_SECRET must be at least 32 characters.")
    return settings
