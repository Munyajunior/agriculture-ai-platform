# services/model-registry/app/api/v1/__init__.py
"""API v1 router for Model Registry"""

from fastapi import APIRouter
from . import deployment, metrics, models

api_router = APIRouter()

api_router.include_router(models.router, prefix="/models", tags=["models"])
api_router.include_router(deployment.router, prefix="/deployments", tags=["deployments"])
api_router.include_router(metrics.router, prefix="/metrics", tags=["metrics"])
