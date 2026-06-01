# services/ai-service/app/api/v1/__init__.py
"""API v1 router for AI Service"""

from fastapi import APIRouter
from . import predictions, models, health

api_router = APIRouter()

api_router.include_router(predictions.router, prefix="/predict", tags=["predictions"])
api_router.include_router(models.router, prefix="/models", tags=["models"])
api_router.include_router(health.router, prefix="/health", tags=["health"])