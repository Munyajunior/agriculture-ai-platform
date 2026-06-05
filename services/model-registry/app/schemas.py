# services/model-registry/app/schemas.py
"""Pydantic schemas for Model Registry"""

from datetime import datetime
from typing import Optional, List, Dict, Any
from uuid import UUID
from pydantic import BaseModel, Field, validator

from .database import ModelStatus, ModelFramework


class ModelCreate(BaseModel):
    """Model creation schema"""
    version: str = Field(..., regex=r'^\d+\.\d+\.\d+$')
    model_type: str = Field(..., description="mobilenetv3, resnet50, efficientnet, yolov8")
    framework: ModelFramework
    num_classes: Optional[int] = Field(default=15)
    classes: Optional[List[str]] = Field(default=[])
    input_shape: Optional[List[int]] = Field(default=[224, 224, 3])
    output_shape: Optional[List[int]] = Field(default=[15])
    training_dataset: Optional[str] = None
    training_epochs: Optional[int] = None
    training_batch_size: Optional[int] = None
    accuracy: Optional[float] = Field(None, ge=0, le=1)
    precision: Optional[float] = Field(None, ge=0, le=1)
    recall: Optional[float] = Field(None, ge=0, le=1)
    f1_score: Optional[float] = Field(None, ge=0, le=1)
    metadata: Optional[Dict[str, Any]] = Field(default={})
    created_by: Optional[str] = "system"
    
    @validator('version')
    def validate_version(cls, v):
        parts = v.split('.')
        if len(parts) != 3:
            raise ValueError('Version must be in format X.Y.Z')
        return v


class ModelResponse(BaseModel):
    """Model response schema"""
    id: UUID
    version: str
    model_type: str
    model_framework: ModelFramework
    num_classes: int
    classes: List[str]
    input_shape: List[int]
    output_shape: List[int]
    accuracy: Optional[float]
    precision: Optional[float]
    recall: Optional[float]
    f1_score: Optional[float]
    model_size_mb: Optional[float]
    inference_time_ms: Optional[float]
    status: ModelStatus
    is_active: bool
    is_deployed: bool
    created_at: datetime
    updated_at: datetime
    deployed_at: Optional[datetime]
    metadata: Dict[str, Any]
    created_by: Optional[str]
    
    class Config:
        from_attributes = True


class ModelUpdate(BaseModel):
    """Model update schema"""
    status: Optional[ModelStatus] = None
    is_active: Optional[bool] = None
    accuracy: Optional[float] = None
    precision: Optional[float] = None
    recall: Optional[float] = None
    f1_score: Optional[float] = None
    inference_time_ms: Optional[float] = None
    metadata: Optional[Dict[str, Any]] = None


class ModelListResponse(BaseModel):
    """Model list response"""
    total: int
    models: List[ModelResponse]
    limit: int
    offset: int


class ModelCompareResponse(BaseModel):
    """Model comparison response"""
    models: List[Dict[str, Any]]
    best_accuracy: Optional[str]
    best_f1: Optional[str]
    smallest_size: Optional[str]


class DeploymentCreate(BaseModel):
    """Deployment creation schema"""
    environment: str = Field(..., regex='^(development|staging|production)$')
    deployed_by: str
    metadata: Optional[Dict[str, Any]] = Field(default={})


class DeploymentResponse(BaseModel):
    """Deployment response schema"""
    id: UUID
    model_id: UUID
    environment: str
    endpoint_url: Optional[str]
    deployed_by: str
    deployed_at: datetime
    status: str
    metadata: Dict[str, Any]
    
    class Config:
        from_attributes = True


class MetricCreate(BaseModel):
    """Metric creation schema"""
    accuracy: Optional[float] = None
    precision: Optional[float] = None
    recall: Optional[float] = None
    f1_score: Optional[float] = None
    latency_p50: Optional[float] = None
    latency_p95: Optional[float] = None
    latency_p99: Optional[float] = None
    throughput: Optional[float] = None
    cpu_usage_percent: Optional[float] = None
    memory_usage_mb: Optional[float] = None
    gpu_usage_percent: Optional[float] = None
    gpu_memory_mb: Optional[float] = None
    total_predictions: Optional[int] = 0
    successful_predictions: Optional[int] = 0
    avg_confidence: Optional[float] = None


class MetricResponse(BaseModel):
    """Metric response schema"""
    id: UUID
    model_id: UUID
    accuracy: Optional[float]
    precision: Optional[float]
    recall: Optional[float]
    f1_score: Optional[float]
    latency_p50: Optional[float]
    latency_p95: Optional[float]
    latency_p99: Optional[float]
    throughput: Optional[float]
    total_predictions: int
    successful_predictions: int
    avg_confidence: Optional[float]
    timestamp: datetime
    
    class Config:
        from_attributes = True