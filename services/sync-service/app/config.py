# services/sync-service/app/config.py
"""Configuration management for Sync Service"""

from typing import Annotated, List, Optional
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict
from pydantic import Field, field_validator


class Settings(BaseSettings):
    """Application settings"""
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore"
    )
    
    # Application
    APP_NAME: str = "Sync Service"
    DEBUG: bool = Field(default=False)
    ENVIRONMENT: str = Field(default="development")
    LOG_LEVEL: str = Field(default="INFO")
    
    # Server
    HOST: str = "0.0.0.0"
    PORT: int = 8006
    
    # Database
    DATABASE_URL: str = Field(default="postgresql://agri_user:secure_password@localhost:5432/agriculture_ai")
    
    # Redis
    REDIS_URL: str = Field(default="redis://localhost:6379/0")
    REDIS_PASSWORD: Optional[str] = None
    
    # Sync configuration
    SYNC_BATCH_SIZE: int = Field(default=100)
    SYNC_INTERVAL_SECONDS: int = Field(default=30)
    SYNC_RETRY_MAX: int = Field(default=5)
    SYNC_RETRY_DELAY_SECONDS: int = Field(default=60)
    SYNC_CONFLICT_STRATEGY: str = Field(default="last_write_wins")  # last_write_wins, server_wins, client_wins, merge
    
    # Queue configuration
    QUEUE_MAX_SIZE: int = Field(default=10000)
    QUEUE_WORKER_COUNT: int = Field(default=4)
    
    # Device sync
    DEVICE_HEARTBEAT_INTERVAL: int = Field(default=60)  # seconds
    DEVICE_OFFLINE_TIMEOUT: int = Field(default=300)  # seconds
    
    # Data retention
    SYNC_LOG_RETENTION_DAYS: int = Field(default=30)
    CONFLICT_LOG_RETENTION_DAYS: int = Field(default=90)
    
    # Rate limiting
    RATE_LIMIT_SYNC_REQUESTS: int = Field(default=60)  # per minute
    RATE_LIMIT_SYNC_SIZE_MB: int = Field(default=100)  # per request
    
    # CORS
    CORS_ORIGINS: Annotated[List[str], NoDecode] = Field(default=["http://localhost:3000", "http://localhost:8080"])

    @field_validator("DEBUG", mode="before")
    def parse_debug(cls, v) -> bool:
        if isinstance(v, str):
            return v.strip().lower() in {"1", "true", "yes", "on", "debug", "development"}
        return bool(v)

    @field_validator("CORS_ORIGINS", mode="before")
    def split_cors_origins(cls, v) -> List[str]:
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",")]
        return v

settings = Settings()
