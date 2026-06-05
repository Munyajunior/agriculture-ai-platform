# services/media-service/app/config.py
"""Configuration management for Media Service"""

from typing import List, Optional
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, validator


class Settings(BaseSettings):
    """Application settings"""
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore"
    )
    
    # Application
    APP_NAME: str = "Media Service"
    DEBUG: bool = Field(default=False)
    ENVIRONMENT: str = Field(default="development")
    LOG_LEVEL: str = Field(default="INFO")
    
    # Server
    HOST: str = "0.0.0.0"
    PORT: int = 8004
    WORKERS: int = 4
    
    # Database
    DATABASE_URL: str = Field(default="postgresql://user:pass@localhost:5432/agriculture_ai")
    DATABASE_POOL_SIZE: int = 20
    DATABASE_MAX_OVERFLOW: int = 40
    
    # Redis
    REDIS_URL: str = Field(default="redis://localhost:6379/0")
    REDIS_PASSWORD: Optional[str] = None
    REDIS_CACHE_TTL: int = 3600  # 1 hour
    
    # Storage (R2/MinIO/S3 compatible)
    STORAGE_TYPE: str = Field(default="minio")  # minio, s3, r2, local
    STORAGE_ENDPOINT: str = Field(default="localhost:9000")
    STORAGE_ACCESS_KEY: str = Field(default="minioadmin")
    STORAGE_SECRET_KEY: str = Field(default="minioadmin123")
    STORAGE_BUCKET: str = Field(default="agriculture-images")
    STORAGE_REGION: Optional[str] = Field(default="us-east-1")
    STORAGE_SECURE: bool = Field(default=False)
    STORAGE_PUBLIC_URL: Optional[str] = Field(default="http://localhost:9000")
    
    # R2 Specific (Cloudflare)
    R2_ACCOUNT_ID: Optional[str] = None
    R2_ACCESS_KEY_ID: Optional[str] = None
    R2_SECRET_ACCESS_KEY: Optional[str] = None
    R2_BUCKET_NAME: str = Field(default="agriculture-ai")
    
    # Local storage fallback
    LOCAL_STORAGE_PATH: str = Field(default="/app/storage")
    
    # Image processing
    MAX_IMAGE_SIZE_MB: int = Field(default=10)
    ALLOWED_IMAGE_TYPES: List[str] = Field(default=["image/jpeg", "image/png", "image/webp", "image/heic"])
    THUMBNAIL_SIZES: List[tuple] = Field(default=[(64, 64), (256, 256), (512, 512)])
    IMAGE_QUALITY: int = Field(default=85)
    
    # URL signing
    URL_EXPIRY_SECONDS: int = Field(default=3600)
    SIGNING_SECRET: str = Field(default="change-me-in-production")
    
    # CORS
    CORS_ORIGINS: List[str] = Field(default=["http://localhost:3000", "http://localhost:8080"])
    ALLOWED_HOSTS: List[str] = Field(default=["localhost", "127.0.0.1"])
    
    # Rate limiting
    RATE_LIMIT_UPLOADS: int = Field(default=50)  # per minute
    RATE_LIMIT_DOWNLOADS: int = Field(default=200)  # per minute
    
    @validator("STORAGE_TYPE")
    def validate_storage_type(cls, v):
        allowed = ["minio", "s3", "r2", "local"]
        if v not in allowed:
            raise ValueError(f"STORAGE_TYPE must be one of {allowed}")
        return v
    
    @validator("MAX_IMAGE_SIZE_MB")
    def validate_max_size(cls, v):
        if v > 100:
            raise ValueError("MAX_IMAGE_SIZE_MB cannot exceed 100MB")
        return v


settings = Settings()