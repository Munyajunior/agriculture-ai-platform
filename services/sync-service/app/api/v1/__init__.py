# services/sync-service/app/api/v1/__init__.py
"""API v1 router for Sync Service"""

from fastapi import APIRouter
from . import sync, devices, conflicts

api_router = APIRouter()

api_router.include_router(sync.router, prefix="/sync", tags=["sync"])
api_router.include_router(devices.router, prefix="/devices", tags=["devices"])
api_router.include_router(conflicts.router, prefix="/conflicts", tags=["conflicts"])