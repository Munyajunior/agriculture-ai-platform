# services/api-gateway/app/api/v1/__init__.py
"""API v1 router"""

from fastapi import APIRouter
from . import auth, predictions, analytics, sync, devices, models

api_router = APIRouter()

api_router.include_router(auth.router, prefix="/auth", tags=["authentication"])
api_router.include_router(predictions.router, prefix="/predict", tags=["predictions"])
api_router.include_router(analytics.router, prefix="/analytics", tags=["analytics"])
api_router.include_router(sync.router, prefix="/sync", tags=["synchronization"])
api_router.include_router(devices.router, prefix="/devices", tags=["devices"])
api_router.include_router(models.router, prefix="/models", tags=["models"])