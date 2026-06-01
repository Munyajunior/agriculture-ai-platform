# services/ai-service/app/config.py
"""Configuration for AI Service"""

from typing import List, Optional
from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    """AI Service settings"""
    
    # Application
    APP_NAME: str = "AI Service"
    DEBUG: bool = Field(default=False)
    ENVIRONMENT: str = Field(default="development")
    
    # Database
    DATABASE_URL: str = Field(
        default="postgresql://agri_user:password@localhost:5432/agriculture_ai"
    )
    
    # Redis
    REDIS_URL: str = Field(default="redis://localhost:6379/0")
    
    # Model settings
    MODEL_PATH: str = Field(default="/models/mobilenetv3_best.pth")
    MODEL_TYPE: str = Field(default="mobilenetv3")
    NUM_CLASSES: int = Field(default=15)
    USE_ONNX: bool = Field(default=False)
    USE_GPU: bool = Field(default=False)
    
    # Inference settings
    BATCH_SIZE: int = Field(default=32)
    MAX_QUEUE_SIZE: int = Field(default=1000)
    FALLBACK_THRESHOLD: float = Field(default=0.7)
    
    # Model registry
    MODEL_REGISTRY_URL: str = Field(default="http://model-registry:8005")
    AUTO_UPDATE_MODELS: bool = Field(default=True)
    MODEL_UPDATE_INTERVAL_HOURS: int = Field(default=24)
    
    # Storage
    MINIO_ENDPOINT: str = Field(default="minio:9000")
    MINIO_ACCESS_KEY: str = Field(default="minioadmin")
    MINIO_SECRET_KEY: str = Field(default="minioadmin123")
    MINIO_BUCKET: str = Field(default="models")
    
    # Performance
    WORKER_COUNT: int = Field(default=4)
    QUEUE_TIMEOUT_SECONDS: int = Field(default=30)
    
    # Monitoring
    ENABLE_METRICS: bool = Field(default=True)
    PROMETHEUS_PORT: int = Field(default=9090)
    
    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()