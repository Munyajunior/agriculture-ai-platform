# shared/types/agriculture_ai/types/schemas.py
"""Pydantic schemas for API validation"""

from datetime import datetime
from typing import Optional, Dict, Any, List
from uuid import UUID
from pydantic import BaseModel, EmailStr, Field, field_validator
from .enums import CropType, DiseaseType, DeviceType, SyncStatus, PredictionStatus, UserRole


# User schemas
class UserCreate(BaseModel):
    """User registration schema"""
    email: EmailStr
    username: str = Field(..., min_length=3, max_length=50)
    password: str = Field(..., min_length=8)
    full_name: Optional[str] = None
    role: UserRole = UserRole.FARMER
    phone_number: Optional[str] = None
    
    @field_validator('username')
    def validate_username(cls, v):
        if not v.replace('_', '').isalnum():
            raise ValueError('Username must contain only letters, numbers, and underscores')
        return v.lower()
    
    @field_validator('password')
    def validate_password(cls, v):
        if not any(c.isupper() for c in v):
            raise ValueError('Password must contain at least one uppercase letter')
        if not any(c.islower() for c in v):
            raise ValueError('Password must contain at least one lowercase letter')
        if not any(c.isdigit() for c in v):
            raise ValueError('Password must contain at least one number')
        return v

class UserResponse(BaseModel):
    """User response schema"""
    id: UUID
    email: EmailStr
    username: str
    full_name: Optional[str]
    role: str
    is_active: bool
    is_verified: bool
    phone_number: Optional[str]
    profile_picture_url: Optional[str]
    created_at: datetime
    last_login: Optional[datetime]
    
    class Config:
        from_attributes = True


class LoginRequest(BaseModel):
    """Login request schema"""
    username: str
    password: str


class TokenResponse(BaseModel):
    """Token response schema"""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserResponse


class RefreshTokenRequest(BaseModel):
    """Refresh token request"""
    refresh_token: str


class ChangePasswordRequest(BaseModel):
    """Change password request"""
    current_password: str
    new_password: str = Field(..., min_length=8)
    
    @field_validator('new_password')
    def validate_password(cls, v):
        if not any(c.isupper() for c in v):
            raise ValueError('Password must contain at least one uppercase letter')
        if not any(c.islower() for c in v):
            raise ValueError('Password must contain at least one lowercase letter')
        if not any(c.isdigit() for c in v):
            raise ValueError('Password must contain at least one number')
        return v


class ForgotPasswordRequest(BaseModel):
    """Forgot password request"""
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    """Reset password request"""
    token: str
    new_password: str = Field(..., min_length=8)


class VerifyEmailRequest(BaseModel):
    """Verify email request"""
    token: str


class UpdateProfileRequest(BaseModel):
    """Update profile request"""
    full_name: Optional[str] = None
    phone_number: Optional[str] = None
    preferences: Optional[Dict[str, Any]] = None


# Farm schemas
class FarmCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    location: Optional[str] = None
    latitude: Optional[float] = Field(None, ge=-90, le=90)
    longitude: Optional[float] = Field(None, ge=-180, le=180)
    crop_type: CropType
    area_hectares: Optional[float] = Field(None, ge=0)
    soil_type: Optional[str] = None
    irrigation_type: Optional[str] = None


class FarmResponse(FarmCreate):
    id: UUID
    user_id: UUID
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


# Prediction schemas
class PredictionRequest(BaseModel):
    image_base64: Optional[str] = None
    image_url: Optional[str] = None
    farm_id: Optional[UUID] = None
    device_type: DeviceType = DeviceType.MOBILE
    use_edge_inference: bool = False
    location_lat: Optional[float] = None
    location_lon: Optional[float] = None
    
    @field_validator('image_base64', 'image_url')
    def validate_image_source(cls, v, values):
        if 'image_base64' not in values and 'image_url' not in values:
            raise ValueError('Either image_base64 or image_url must be provided')
        return v


class PredictionResponse(BaseModel):
    id: UUID
    scan_id: UUID
    disease_type: DiseaseType
    confidence_score: float = Field(..., ge=0, le=1)
    inference_source: str
    processing_time_ms: Optional[int]
    treatments: List[Dict[str, Any]]
    image_url: str
    created_at: datetime
    
    class Config:
        from_attributes = True


# Sync schemas
class SyncRequest(BaseModel):
    device_id: str
    scans: List[Dict[str, Any]]
    predictions: List[Dict[str, Any]]
    telemetry: Optional[List[Dict[str, Any]]] = None


class SyncResponse(BaseModel):
    synced_scans: int
    synced_predictions: int
    failed_items: List[str]
    new_models_available: bool
    latest_model_version: Optional[str]
    sync_id: UUID


# Device schemas
class DeviceRegister(BaseModel):
    device_name: str
    device_type: DeviceType
    device_id: str
    firmware_version: Optional[str] = None
    capabilities: Optional[Dict[str, Any]] = None


class DeviceResponse(DeviceRegister):
    id: UUID
    user_id: UUID
    is_active: bool
    registered_at: datetime
    last_heartbeat: Optional[datetime]
    
    class Config:
        from_attributes = True


# Analytics schemas
class AnalyticsQuery(BaseModel):
    start_date: datetime
    end_date: datetime
    crop_type: Optional[CropType] = None
    disease_type: Optional[DiseaseType] = None
    group_by: Optional[str] = "day"


class AnalyticsResponse(BaseModel):
    total_scans: int
    total_predictions: int
    disease_distribution: Dict[str, int]
    confidence_distribution: Dict[str, float]
    inference_source_distribution: Dict[str, int]
    average_processing_time: float
    top_diseases: List[Dict[str, Any]]
    timeline_data: List[Dict[str, Any]]