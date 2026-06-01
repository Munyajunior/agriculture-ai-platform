# services/ai-service/app/schemas/model.py
"""Pydantic schemas for model management"""

from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from uuid import UUID


class ModelInfo(BaseModel):
    """Model information schema"""
    
    id: Optional[UUID] = None
    version: str
    model_type: str
    model_architecture: Optional[str] = None
    model_url: Optional[str] = None
    onnx_url: Optional[str] = None
    quantized_url: Optional[str] = None
    input_shape: List[int] = [3, 224, 224]
    output_shape: List[int] = [15]
    classes: List[str] = []
    accuracy: Optional[float] = None
    precision: Optional[float] = None
    recall: Optional[float] = None
    f1_score: Optional[float] = None
    model_size_mb: Optional[float] = None
    is_active: bool = False
    is_deployed: bool = False
    deployment_date: Optional[datetime] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ModelVersion(BaseModel):
    """Model version schema"""
    
    version: str
    release_notes: Optional[str] = None
    is_latest: bool = False
    published_at: datetime = Field(default_factory=datetime.utcnow)


class ModelDownloadRequest(BaseModel):
    """Request to download a model"""
    
    version: str
    destination_path: Optional[str] = None
    format: str = "onnx"


class ModelActivateRequest(BaseModel):
    """Request to activate a model"""
    
    version: str
    load_immediately: bool = True


class ModelMetadata(BaseModel):
    """Model metadata schema"""
    
    name: str
    description: Optional[str] = None
    author: Optional[str] = None
    license: Optional[str] = None
    framework: str = "pytorch"
    tags: List[str] = Field(default_factory=list)