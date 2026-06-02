# services/api-gateway/app/clients/__init__.py
"""Service clients for API Gateway"""

from .auth_service import AuthServiceClient
from .ai_service import AIServiceClient
from .analytics_service import AnalyticsServiceClient
from .media_service import MediaServiceClient
from .model_registry import ModelRegistryClient
from .sync_service import SyncServiceClient

__all__ = [
    "AuthServiceClient",
    "AIServiceClient",
    "AnalyticsServiceClient",
    "MediaServiceClient",
    "ModelRegistryClient",
    "SyncServiceClient",
]