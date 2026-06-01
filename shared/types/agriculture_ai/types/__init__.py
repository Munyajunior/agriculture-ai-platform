# shared/types/agriculture_ai/types/__init__.py
"""Shared type definitions for Agriculture AI Platform"""

from .enums import (
    DiseaseType,
    CropType,
    PredictionStatus,
    DeviceType,
    SyncStatus,
    UserRole,
)
from .models import (
    User,
    Farm,
    Scan,
    Prediction,
    Disease,
    Treatment,
    Device,
    Telemetry,
    ModelVersion,
    SyncLog,
)
from .schemas import (
    UserCreate,
    UserResponse,
    LoginRequest,
    TokenResponse,
    PredictionRequest,
    PredictionResponse,
    SyncRequest,
    SyncResponse,
)

__all__ = [
    # Enums
    "DiseaseType",
    "CropType",
    "PredictionStatus",
    "DeviceType",
    "SyncStatus",
    "UserRole",
    # Models
    "User",
    "Farm",
    "Scan",
    "Prediction",
    "Disease",
    "Treatment",
    "Device",
    "Telemetry",
    "ModelVersion",
    "SyncLog",
    # Schemas
    "UserCreate",
    "UserResponse",
    "LoginRequest",
    "TokenResponse",
    "PredictionRequest",
    "PredictionResponse",
    "SyncRequest",
    "SyncResponse",
]