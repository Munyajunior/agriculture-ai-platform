# services/api-gateway/app/config.py
"""Configuration management for API Gateway"""

from typing import List
from pydantic_settings import BaseSettings
from pydantic import Field, field_validator


class Settings(BaseSettings):
    """Application settings"""
    
    # Application
    APP_NAME: str = "API Gateway"
    DEBUG: bool = Field(default=False)
    ENVIRONMENT: str = Field(default="development")
    
    # Security
    SECRET_KEY: str = Field(..., min_length=32)
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    
    # CORS
    CORS_ORIGINS: List[str] = Field(default_factory=lambda: ["http://localhost:3000", "http://localhost:8080"])
    ALLOWED_HOSTS: List[str] = Field(default_factory=lambda: ["localhost", "127.0.0.1"])

    @field_validator("DEBUG", mode="before")
    def parse_debug(cls, v) -> bool:
        if isinstance(v, str):
            return v.strip().lower() in {"1", "true", "yes", "on", "debug", "development"}
        return bool(v)

    @field_validator("CORS_ORIGINS", mode="before")
    def split_cors_origins(cls, v)-> List[str]:
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",")]
        return v

    @field_validator("ALLOWED_HOSTS", mode="before")
    def split_allowed_hosts(cls, v)-> List[str]:
        if isinstance(v, str):
            return [host.strip() for host in v.split(",")]
        return v

    # Redis
    REDIS_URL: str = Field(default="redis://localhost:6379/0")
    
    # Service URLs
    AUTH_SERVICE_URL: str = Field(default="http://auth-service:8001")
    AI_SERVICE_URL: str = Field(default="http://ai-service:8002")
    ANALYTICS_SERVICE_URL: str = Field(default="http://analytics-service:8003")
    MEDIA_SERVICE_URL: str = Field(default="http://media-service:8004")
    MODEL_REGISTRY_URL: str = Field(default="http://model-registry:8005")
    SYNC_SERVICE_URL: str = Field(default="http://sync-service:8006")
    
    # Rate limiting
    RATE_LIMIT_REQUESTS: int = Field(default=100)
    RATE_LIMIT_PERIOD: int = Field(default=60)  # seconds
    
    # Logging
    LOG_LEVEL: str = Field(default="INFO")
    
    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()
