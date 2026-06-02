# services/api-gateway/app/schemas/__init__.py
"""Pydantic schemas for API Gateway"""

from .prediction import (
    PredictionRequest,
    PredictionResponse,
    BatchPredictionRequest,
    TreatmentRecommendation
)
from .auth import (
    UserRegister,
    UserLogin,
    TokenResponse,
    UserResponse
)
from .analytics import (
    AnalyticsQuery,
    AnalyticsResponse,
    DashboardStats
)
from .sync import (
    SyncRequest,
    SyncResponse,
    OfflineData
)

__all__ = [
    "PredictionRequest",
    "PredictionResponse",
    "BatchPredictionRequest",
    "TreatmentRecommendation",
    "UserRegister",
    "UserLogin",
    "TokenResponse",
    "UserResponse",
    "AnalyticsQuery",
    "AnalyticsResponse",
    "DashboardStats",
    "SyncRequest",
    "SyncResponse",
    "OfflineData",
]
