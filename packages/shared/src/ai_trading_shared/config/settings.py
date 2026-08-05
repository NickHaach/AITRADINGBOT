"""Application settings loaded from environment variables."""

from __future__ import annotations

from functools import lru_cache
from typing import List, Literal, Optional

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Central configuration. All services consume a subset via DI."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_env: Literal["development", "staging", "production", "test"] = "development"
    app_name: str = "ai-trading-platform"
    log_level: str = "INFO"
    secret_key: SecretStr = Field(default=SecretStr("dev-only-change-me"))
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 30
    jwt_refresh_token_expire_days: int = 7

    api_host: str = "0.0.0.0"
    api_port: int = 8000
    dashboard_url: str = "http://localhost:3000"
    cors_origins: str = "http://localhost:3000"

    database_url: str = (
        "postgresql+asyncpg://trading:trading_dev_password@localhost:5432/ai_trading"
    )
    # Opt-in durable dual-write for market bars/features and graph snapshots.
    enable_sql_persistence: bool = False
    redis_url: str = "redis://localhost:6379/0"
    celery_broker_url: str = "redis://localhost:6379/1"
    celery_result_backend: str = "redis://localhost:6379/2"
    # Shared filesystem for GBM joblib artifacts (mount in Docker)
    model_artifact_dir: str = "artifacts"

    qdrant_url: str = "http://localhost:6333"
    qdrant_collection_news: str = "news_embeddings"
    qdrant_api_key: Optional[SecretStr] = None

    openai_api_key: Optional[SecretStr] = None
    openai_model: str = "gpt-4o-mini"
    local_llm_base_url: str = "http://localhost:11434/v1"
    local_llm_model: str = "llama3.1"
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    use_mock_llm: bool = True

    newsapi_key: Optional[SecretStr] = None
    finnhub_api_key: Optional[SecretStr] = None
    alpha_vantage_api_key: Optional[SecretStr] = None
    use_mock_news: bool = True

    polygon_api_key: Optional[SecretStr] = None
    use_mock_market_data: bool = True

    execution_mode: Literal["paper", "live"] = "paper"
    enable_live_trading: bool = False
    broker_alpaca_api_key: Optional[SecretStr] = None
    broker_alpaca_secret_key: Optional[SecretStr] = None
    broker_alpaca_base_url: str = "https://paper-api.alpaca.markets"

    risk_max_position_pct: float = 0.05
    risk_max_portfolio_risk_pct: float = 0.20
    risk_daily_loss_limit_pct: float = 0.02
    risk_max_sector_exposure_pct: float = 0.25
    risk_max_country_exposure_pct: float = 0.40
    risk_max_drawdown_pct: float = 0.15

    prometheus_enabled: bool = True

    @property
    def cors_origin_list(self) -> List[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"

    def assert_live_trading_allowed(self) -> None:
        """Raise if live trading is requested without dual enablement."""
        if self.execution_mode == "live" and not self.enable_live_trading:
            raise RuntimeError(
                "Live trading blocked: set ENABLE_LIVE_TRADING=true and EXECUTION_MODE=live"
            )
        if self.enable_live_trading and self.execution_mode != "live":
            raise RuntimeError("ENABLE_LIVE_TRADING requires EXECUTION_MODE=live")


@lru_cache()
def get_settings() -> Settings:
    return Settings()
