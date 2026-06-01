# services/analytics-service/app/api/v1/__init__.py
"""Analytics API v1 router"""

from fastapi import APIRouter
from . import dashboard, diseases, predictions, reports, alerts, export

api_router = APIRouter()

api_router.include_router(dashboard.router, prefix="/dashboard", tags=["dashboard"])
api_router.include_router(diseases.router, prefix="/diseases", tags=["diseases"])
api_router.include_router(predictions.router, prefix="/predictions", tags=["predictions"])
api_router.include_router(reports.router, prefix="/reports", tags=["reports"])
api_router.include_router(alerts.router, prefix="/alerts", tags=["alerts"])
api_router.include_router(export.router, prefix="/export", tags=["export"])