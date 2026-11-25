"""
StateFlow Core Configuration

Centralized configuration management using Pydantic Settings.
All settings are loaded from environment variables with sensible defaults.
"""
from functools import lru_cache
from typing import List, Optional

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # Application
    APP_NAME: str = "StateFlow"
    APP_VERSION: str = "1.0.0"
    ENVIRONMENT: str = Field(default="development", pattern="^(development|staging|production|testing)$")
    DEBUG: bool = True
    LOG_LEVEL: str = Field(default="INFO", pattern="^(DEBUG|INFO|WARNING|ERROR|CRITICAL)$")

    # Server
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    WORKERS: int = 1

    # Database
    DATABASE_URL: str = Field(
        default="postgresql+asyncpg://stateflow:stateflow_dev_password@localhost:5432/stateflow"
    )
    DATABASE_POOL_SIZE: int = 10
    DATABASE_MAX_OVERFLOW: int = 20
    DATABASE_POOL_TIMEOUT: int = 30
    DATABASE_POOL_RECYCLE: int = 3600

    # Redis
    REDIS_URL: str = Field(default="redis://localhost:6379/0")
    REDIS_MAX_CONNECTIONS: int = 50
    REDIS_SOCKET_TIMEOUT: int = 5
    REDIS_SOCKET_CONNECT_TIMEOUT: int = 5

    # RabbitMQ
    RABBITMQ_URL: str = Field(default="amqp://stateflow:stateflow_dev_password@localhost:5672/stateflow")
    RABBITMQ_CONNECTION_TIMEOUT: int = 10
    RABBITMQ_HEARTBEAT: int = 60

    # Security
    SECRET_KEY: str = Field(default="dev-secret-key-change-in-production-min-32-chars")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    PASSWORD_MIN_LENGTH: int = 8
    BCRYPT_ROUNDS: int = 12

    # CORS
    CORS_ORIGINS: List[str] = Field(default=["http://localhost:3000"])
    CORS_ALLOW_CREDENTIALS: bool = True
    CORS_ALLOW_METHODS: List[str] = Field(default=["*"])
    CORS_ALLOW_HEADERS: List[str] = Field(default=["*"])

    # Rate Limiting
    RATE_LIMIT_ENABLED: bool = True
    RATE_LIMIT_REQUESTS: int = 100
    RATE_LIMIT_WINDOW_SECONDS: int = 60

    # Celery
    CELERY_BROKER_URL: str = Field(default="amqp://stateflow:stateflow_dev_password@rabbitmq:5672/stateflow")
    CELERY_RESULT_BACKEND: str = Field(default="redis://redis:6379/1")
    CELERY_TASK_SERIALIZER: str = "json"
    CELERY_RESULT_SERIALIZER: str = "json"
    CELERY_ACCEPT_CONTENT: List[str] = Field(default=["json"])
    CELERY_TIMEZONE: str = "UTC"
    CELERY_TASK_TRACK_STARTED: bool = True
    CELERY_TASK_TIME_LIMIT: int = 300
    CELERY_WORKER_PREFETCH_MULTIPLIER: int = 4

    # Saga Engine
    SAGA_MAX_RETRIES: int = 3
    SAGA_RETRY_BASE_DELAY: float = 1.0
    SAGA_RETRY_MAX_DELAY: float = 60.0
    SAGA_RETRY_EXPONENTIAL_BASE: float = 2.0
    SAGA_STEP_TIMEOUT_SECONDS: int = 300
    SAGA_COMPENSATION_TIMEOUT_SECONDS: int = 300

    # Idempotency
    IDEMPOTENCY_TTL_HOURS: int = 24
    IDEMPOTENCY_CLEANUP_INTERVAL_HOURS: int = 1

    # Outbox
    OUTBOX_POLL_INTERVAL_SECONDS: float = 1.0
    OUTBOX_BATCH_SIZE: int = 100
    OUTBOX_MAX_RETRIES: int = 5

    # Monitoring
    METRICS_ENABLED: bool = True
    METRICS_PORT: int = 9090
    TRACING_ENABLED: bool = True
    TRACING_SAMPLE_RATE: float = 1.0
    OTEL_EXPORTER_OTLP_ENDPOINT: str = "http://localhost:4317"
    OTLP_ENDPOINT: str = "http://localhost:4317"
    OTLP_INSECURE: bool = True

    # Health Checks
    HEALTH_CHECK_INTERVAL_SECONDS: int = 30

    # Pagination
    DEFAULT_PAGE_SIZE: int = 20
    MAX_PAGE_SIZE: int = 100

    @field_validator("SECRET_KEY")
    @classmethod
    def validate_secret_key(cls, v: str) -> str:
        # Allow shorter keys in development and testing
        env = cls.model_fields["ENVIRONMENT"].default
        if len(v) < 32 and env not in ("development", "testing"):
            raise ValueError("SECRET_KEY must be at least 32 characters in production")
        return v

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def parse_cors_origins(cls, v: str | List[str]) -> List[str]:
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",")]
        return v


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


# Export settings instance
settings = get_settings()