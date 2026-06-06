# services/analytics-service/app/api/v1/__init__.py
"""Analytics API v1 router"""

from fastapi import APIRouter
from . import alerts, analytics, dashboard, diseases, reports

api_router = APIRouter()

api_router.include_router(dashboard.router, prefix="/dashboard", tags=["dashboard"])
api_router.include_router(diseases.router, prefix="/diseases", tags=["diseases"])
api_router.include_router(analytics.router, prefix="/analytics", tags=["analytics"])
api_router.include_router(reports.router, prefix="/reports", tags=["reports"])
api_router.include_router(alerts.router, prefix="/alerts", tags=["alerts"])
