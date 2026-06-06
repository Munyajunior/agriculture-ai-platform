# services/media-service/app/api/v1/__init__.py
"""API v1 router for Media Service"""

from fastapi import APIRouter
from . import download, upload

api_router = APIRouter()

api_router.include_router(upload.router, prefix="/upload", tags=["upload"])
api_router.include_router(download.router, prefix="/download", tags=["download"])
