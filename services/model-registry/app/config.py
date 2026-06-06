# services/model-registry/app/config.py
"""Configuration management for Model Registry"""

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
    APP_NAME: str = "Model Registry"
    DEBUG: bool = Field(default=False)
    ENVIRONMENT: str = Field(default="development")
    LOG_LEVEL: str = Field(default="INFO")
    
    # Server
    HOST: str = "0.0.0.0"
    PORT: int = 8005
    
    # Database
    DATABASE_URL: str = Field(default="postgresql://agri_user:secure_password@localhost:5432/agriculture_ai")
    
    # Redis
    REDIS_URL: str = Field(default="redis://localhost:6379/0")
    REDIS_PASSWORD: Optional[str] = None
    
    # Model Storage
    MODEL_STORAGE_TYPE: str = Field(default="minio")  # minio, s3, local
    MODEL_STORAGE_ENDPOINT: str = Field(default="localhost:9000")
    MODEL_STORAGE_ACCESS_KEY: str = Field(default="minioadmin")
    MODEL_STORAGE_SECRET_KEY: str = Field(default="minioadmin123")
    MODEL_STORAGE_BUCKET: str = Field(default="ai-models")
    MODEL_STORAGE_SECURE: bool = Field(default=False)
    
    # Local model cache
    MODEL_CACHE_PATH: str = Field(default="/app/models/cache")
    MAX_CACHED_MODELS: int = Field(default=5)
    
    # Model configurations
    SUPPORTED_MODEL_TYPES: List[str] = Field(default=["mobilenetv3", "resnet50", "efficientnet", "yolov8"])
    DEFAULT_MODEL_TYPE: str = "mobilenetv3"
    DEFAULT_NUM_CLASSES: int = 15
    
    # MLflow
    MLFLOW_TRACKING_URI: Optional[str] = Field(default=None)
    MLFLOW_EXPERIMENT_NAME: str = Field(default="plant-disease-detection")
    
    # CORS
    CORS_ORIGINS: Annotated[List[str], NoDecode] = Field(default=["http://localhost:3000", "http://localhost:8080"])
    
    # Monitoring
    ENABLE_MODEL_MONITORING: bool = Field(default=True)
    MODEL_METRICS_RETENTION_DAYS: int = Field(default=30)
    
    # Security
    API_KEY: str = Field(default="change-me-in-production")

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
