# services/model-registry/app/database.py
"""Database models for Model Registry"""

from datetime import datetime
from typing import Optional, Dict, Any, List
from uuid import UUID, uuid4
from sqlalchemy import (
    Column, String, DateTime, Integer, Float, Boolean, 
    JSON, ForeignKey, Table, Index, Text, Enum, text
)
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.ext.asyncio import (
    AsyncSession, create_async_engine, async_sessionmaker
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
import enum
import logging

from .config import settings

logger = logging.getLogger(__name__)

# Database engine
engine = create_async_engine(
    settings.DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://"),
    pool_size=20,
    max_overflow=40,
    echo=settings.DEBUG
)

AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)
Base = declarative_base()


class ModelStatus(str, enum.Enum):
    """Model status enum"""
    DRAFT = "draft"
    STAGING = "staging"
    PRODUCTION = "production"
    ARCHIVED = "archived"
    FAILED = "failed"


class ModelFramework(str, enum.Enum):
    """Model framework enum"""
    PYTORCH = "pytorch"
    TENSORFLOW = "tensorflow"
    ONNX = "onnx"
    TENSORRT = "tensorrt"


class ModelVersion(Base):
    """Model version metadata"""
    __tablename__ = "model_versions"
    
    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    version = Column(String(50), nullable=False, unique=True)
    model_type = Column(String(50), nullable=False)  # mobilenetv3, resnet50, etc.
    model_framework = Column(Enum(ModelFramework), nullable=False)
    
    # Model files
    model_path = Column(String(500))  # Path in storage
    onnx_path = Column(String(500))
    quantized_path = Column(String(500))
    tensorrt_path = Column(String(500))
    
    # Model metadata
    input_shape = Column(JSON, default=list)
    output_shape = Column(JSON, default=list)
    num_classes = Column(Integer)
    classes = Column(JSON, default=list)  # List of disease classes
    
    # Performance metrics
    accuracy = Column(Float)
    precision = Column(Float)
    recall = Column(Float)
    f1_score = Column(Float)
    model_size_mb = Column(Float)
    inference_time_ms = Column(Float)
    
    # Training info
    training_dataset = Column(String(200))
    training_epochs = Column(Integer)
    training_batch_size = Column(Integer)
    training_config = Column(JSON, default=dict)
    
    # Status
    status = Column(Enum(ModelStatus), default=ModelStatus.DRAFT)
    is_active = Column(Boolean, default=False)
    is_deployed = Column(Boolean, default=False)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    deployed_at = Column(DateTime)
    
    # Additional metadata
    metadata_ = Column("metadata", JSON, default=dict)
    created_by = Column(String(100))
    
    # Relationships
    deployments = relationship("ModelDeployment", back_populates="model")
    metrics = relationship("ModelMetric", back_populates="model")
    
    __table_args__ = (
        Index("idx_model_version", "version"),
        Index("idx_model_type_status", "model_type", "status"),
        Index("idx_model_active", "is_active"),
        Index("idx_model_deployed", "is_deployed"),
    )


class ModelDeployment(Base):
    """Model deployment history"""
    __tablename__ = "model_deployments"
    
    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    model_id = Column(PGUUID(as_uuid=True), ForeignKey("model_versions.id", ondelete="CASCADE"))
    environment = Column(String(50))  # development, staging, production
    endpoint_url = Column(String(500))
    deployed_by = Column(String(100))
    deployed_at = Column(DateTime, default=datetime.utcnow)
    status = Column(String(50))  # success, failed, rolling_back
    rollback_from = Column(PGUUID(as_uuid=True))
    metadata_ = Column("metadata", JSON, default=dict)
    
    # Relationships
    model = relationship("ModelVersion", back_populates="deployments")
    
    __table_args__ = (
        Index("idx_deployment_model", "model_id"),
        Index("idx_deployment_env_time", "environment", "deployed_at"),
    )


class ModelMetric(Base):
    """Model performance metrics over time"""
    __tablename__ = "model_metrics"
    
    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    model_id = Column(PGUUID(as_uuid=True), ForeignKey("model_versions.id", ondelete="CASCADE"))
    
    # Performance metrics
    accuracy = Column(Float)
    precision = Column(Float)
    recall = Column(Float)
    f1_score = Column(Float)
    latency_p50 = Column(Float)
    latency_p95 = Column(Float)
    latency_p99 = Column(Float)
    throughput = Column(Float)  # requests per second
    
    # Resource usage
    cpu_usage_percent = Column(Float)
    memory_usage_mb = Column(Float)
    gpu_usage_percent = Column(Float)
    gpu_memory_mb = Column(Float)
    
    # Data drift metrics
    feature_drift_score = Column(Float)
    prediction_drift_score = Column(Float)
    
    # Business metrics
    total_predictions = Column(Integer, default=0)
    successful_predictions = Column(Integer, default=0)
    avg_confidence = Column(Float)
    
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Relationships
    model = relationship("ModelVersion", back_populates="metrics")
    
    __table_args__ = (
        Index("idx_metric_model_time", "model_id", "timestamp"),
        Index("idx_metric_timestamp", "timestamp"),
    )


class ModelExperiment(Base):
    """MLflow experiment tracking"""
    __tablename__ = "model_experiments"
    
    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    experiment_id = Column(String(100), unique=True, nullable=False)
    experiment_name = Column(String(200), nullable=False)
    run_id = Column(String(100))
    run_name = Column(String(200))
    
    # Parameters
    parameters = Column(JSON, default=dict)
    metrics = Column(JSON, default=dict)
    artifacts = Column(JSON, default=list)
    
    # Model info
    model_version_id = Column(PGUUID(as_uuid=True), ForeignKey("model_versions.id"))
    
    status = Column(String(50))
    started_at = Column(DateTime)
    ended_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    __table_args__ = (
        Index("idx_experiment_name", "experiment_name"),
        Index("idx_experiment_run", "run_id"),
    )


async def init_db():
    """Initialize database"""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.execute(text("""
            DO $$
            BEGIN
                IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'modelframework') THEN
                    CREATE TYPE modelframework AS ENUM ('PYTORCH', 'TENSORFLOW', 'ONNX', 'TENSORRT');
                END IF;
                IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'modelstatus') THEN
                    CREATE TYPE modelstatus AS ENUM ('DRAFT', 'VALIDATING', 'VALIDATED', 'PRODUCTION', 'ARCHIVED', 'FAILED');
                END IF;
            END
            $$;
        """))
        await conn.execute(text("""
            ALTER TABLE model_versions
            ADD COLUMN IF NOT EXISTS model_framework modelframework NOT NULL DEFAULT 'PYTORCH',
            ADD COLUMN IF NOT EXISTS model_path varchar(500),
            ADD COLUMN IF NOT EXISTS onnx_path varchar(500),
            ADD COLUMN IF NOT EXISTS quantized_path varchar(500),
            ADD COLUMN IF NOT EXISTS tensorrt_path varchar(500),
            ADD COLUMN IF NOT EXISTS input_shape json,
            ADD COLUMN IF NOT EXISTS output_shape json,
            ADD COLUMN IF NOT EXISTS num_classes integer,
            ADD COLUMN IF NOT EXISTS classes json,
            ADD COLUMN IF NOT EXISTS accuracy double precision,
            ADD COLUMN IF NOT EXISTS precision double precision,
            ADD COLUMN IF NOT EXISTS recall double precision,
            ADD COLUMN IF NOT EXISTS f1_score double precision,
            ADD COLUMN IF NOT EXISTS model_size_mb double precision,
            ADD COLUMN IF NOT EXISTS inference_time_ms double precision,
            ADD COLUMN IF NOT EXISTS training_dataset varchar(200),
            ADD COLUMN IF NOT EXISTS training_epochs integer,
            ADD COLUMN IF NOT EXISTS training_batch_size integer,
            ADD COLUMN IF NOT EXISTS training_config json,
            ADD COLUMN IF NOT EXISTS status modelstatus DEFAULT 'DRAFT',
            ADD COLUMN IF NOT EXISTS is_active boolean DEFAULT false,
            ADD COLUMN IF NOT EXISTS is_deployed boolean DEFAULT false,
            ADD COLUMN IF NOT EXISTS created_at timestamp,
            ADD COLUMN IF NOT EXISTS updated_at timestamp,
            ADD COLUMN IF NOT EXISTS deployed_at timestamp,
            ADD COLUMN IF NOT EXISTS metadata json,
            ADD COLUMN IF NOT EXISTS created_by varchar(100)
        """))
        logger.info("Database tables created")


async def get_db() -> AsyncSession:
    """Get database session"""
    async with AsyncSessionLocal() as session:
        yield session
