# services/analytics-service/app/config.py
"""Configuration management for Analytics Service"""

from typing import List, Optional
from pydantic_settings import BaseSettings
from pydantic import Field, field_validator


class Settings(BaseSettings):
    """Application settings"""
    
    # Application
    APP_NAME: str = "Analytics Service"
    DEBUG: bool = Field(default=False)
    ENVIRONMENT: str = Field(default="development")
    
    # Database
    DATABASE_URL: str = Field(default="postgresql://agri_user:password@localhost:5432/agriculture_ai")
    
    # Redis
    REDIS_URL: str = Field(default="redis://localhost:6379/0")
    REDIS_PASSWORD: str = Field(default="")
    
    # Security
    SECRET_KEY: str = Field(..., min_length=32)
    
    # CORS
    CORS_ORIGINS: str = Field(default="http://localhost:3000,http://localhost:8000")

    @field_validator("CORS_ORIGINS", pre=True)
    def split_cors_origins(cls, v) -> List[str]:
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",")]
        return v
    
    # Analytics Settings
    ANALYTICS_CACHE_TTL: int = Field(default=3600)  # 1 hour
    MAX_EXPORT_ROWS: int = Field(default=100000)
    ENABLE_REAL_TIME_METRICS: bool = Field(default=True)
    
    # ML Settings for predictive analytics
    ENABLE_PREDICTIVE_ANALYTICS: bool = Field(default=True)
    FORECAST_DAYS: int = Field(default=30)
    
    # Reporting
    REPORT_STORAGE_PATH: str = Field(default="/reports")
    ENABLE_EMAIL_REPORTS: bool = Field(default=False)
    
    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()