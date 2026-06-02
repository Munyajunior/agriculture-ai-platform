# """Prediction schemas"""

from typing import Optional, List, Dict, Any
from uuid import UUID
from datetime import datetime
from pydantic import BaseModel, Field, validator


class TreatmentRecommendation(BaseModel):
    """Treatment recommendation schema"""
    treatment_type: str
    product_name: Optional[str] = None
    application_method: str
    dosage_instructions: str
    frequency_days: int
    precautions: List[str] = []
    organic_option: bool = False
    effectiveness_rating: float = Field(..., ge=0, le=1)


class PredictionRequest(BaseModel):
    """Prediction request schema"""
    image_base64: Optional[str] = None
    image_url: Optional[str] = None
    farm_id: Optional[UUID] = None
    device_type: str = "mobile"
    use_edge_inference: bool = False
    location_lat: Optional[float] = Field(None, ge=-90, le=90)
    location_lon: Optional[float] = Field(None, ge=-180, le=180)
    
    @validator('image_base64', 'image_url')
    def validate_image_source(cls, v, values):
        if 'image_base64' not in values and 'image_url' not in values:
            raise ValueError('Either image_base64 or image_url must be provided')
        return v


class PredictionResponse(BaseModel):
    """Prediction response schema"""
    id: UUID
    scan_id: UUID
    disease_type: str
    disease_name: str
    confidence_score: float = Field(..., ge=0, le=1)
    inference_source: str  # 'cloud', 'edge', or 'hybrid'
    processing_time_ms: int
    treatments: List[TreatmentRecommendation]
    image_url: str
    thumbnail_url: Optional[str] = None
    created_at: datetime
    
    class Config:
        from_attributes = True


class BatchPredictionRequest(BaseModel):
    """Batch prediction request"""
    images: List[str]  # List of base64 encoded images or URLs
    farm_id: Optional[UUID] = None
    device_type: str = "mobile"


class PredictionHistoryResponse(BaseModel):
    """Prediction history response"""
    total: int
    predictions: List[PredictionResponse]