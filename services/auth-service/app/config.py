# services/auth-service/app/config.py
"""Configuration for Auth Service"""

import http
from typing import List, Optional
from pydantic_settings import BaseSettings
from pydantic import Field, field_validator, SecretStr


class Settings(BaseSettings):
    """Application settings"""
    
    # Application
    APP_NAME: str = "Auth Service"
    DEBUG: bool = Field(default=False)
    ENVIRONMENT: str = Field(default="development")
    
    # Security
    SECRET_KEY: str = Field(..., min_length=32)
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    PASSWORD_RESET_TOKEN_EXPIRE_HOURS: int = 24

    # Security Limits
    MAX_LOGIN_ATTEMPTS: int = 5
    LOCKOUT_DURATION_MINUTES: int = 30
    PASSWORD_HISTORY_COUNT: int = 5
    
    
    # Database
    DATABASE_URL: str = Field(default="postgresql://agri_user:password@localhost:5432/agriculture_ai")
    DATABASE_POOL_SIZE: int = Field(default=20)
    DATABASE_MAX_OVERFLOW: int = Field(default=40)
    
    # Redis
    REDIS_URL: str = Field(default="redis://localhost:6379/0")
    REDIS_PASSWORD: Optional[str] = None
    
    # CORS
    CORS_ORIGINS: List[str] = Field(default_factory=lambda: ["http://localhost:3000", "http://localhost:8080"])

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
    
    # Rate Limiting
    RATE_LIMIT_REQUESTS: int = 5
    RATE_LIMIT_PERIOD: int = 60
    
    # Email Configuration
    SMTP_HOST: str = "smtp.gmail.com"
    SMTP_PORT: int = 587
    SMTP_USER: Optional[str] = None
    SMTP_PASSWORD: Optional[SecretStr] = None
    SMTP_FROM_EMAIL: str = "noreply@agriculture-ai.com"
    SMTP_FROM_NAME: str = "Agriculture AI Platform"

    # Frontend URLs
    FRONTEND_URL: str = "http://localhost:3000"
    RESET_PASSWORD_URL: str = "{frontend_url}/reset-password?token={token}"
    VERIFY_EMAIL_URL: str = "{frontend_url}/verify-email?token={token}"

    # JWT
    JWT_ISSUER: str = "agriculture-ai-platform"
    JWT_AUDIENCE: str = "agriculture-ai-users"
    
    # Two-Factor Authentication
    ENABLE_2FA: bool = False
    TOTP_ISSUER: str = "Agriculture AI Platform"
    TOTP_DIGITS: int = 6
    TOTP_PERIOD: int = 30
    
    # OAuth2
    GOOGLE_CLIENT_ID: Optional[str] = None
    GOOGLE_CLIENT_SECRET: Optional[SecretStr] = None
    GITHUB_CLIENT_ID: Optional[str] = None
    GITHUB_CLIENT_SECRET: Optional[SecretStr] = None
    
    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()
