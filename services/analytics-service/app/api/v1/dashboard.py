# services/analytics-service/app/api/v1/dashboard.py
"""Dashboard analytics endpoints"""

from typing import Optional, Dict, Any
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from app.services.analytics_engine import analytics_engine
from app.services.metrics_service import MetricsService
from app.core.auth import verify_token
from app.schemas.analytics import (
    DashboardSummary,
    TimeSeriesData,
    DiseaseDistribution,
    PerformanceMetrics,
    UserActivityMetrics
)

router = APIRouter()
security = HTTPBearer()
metrics_service = MetricsService()

@router.get("/summary", response_model=DashboardSummary)
async def get_dashboard_summary(
    days: int = Query(30, ge=1, le=365),
    crop_type: Optional[str] = None,
    region: Optional[str] = None,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """Get main dashboard summary statistics"""
    user = await verify_token(credentials.credentials)
    
    summary = await analytics_engine.get_dashboard_summary(
        days=days,
        crop_type=crop_type,
        region=region
    )
    
    return summary

@router.get("/timeseries")
async def get_timeseries_data(
    metric: str = Query(..., pattern="^(scans|predictions|confidence|accuracy)$"),
    days: int = Query(30, ge=1, le=365),
    interval: str = Query("day", pattern="^(hour|day|week|month)$"),
    crop_type: Optional[str] = None,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """Get time series data for specified metric"""
    user = await verify_token(credentials.credentials)
    
    data = await analytics_engine.get_timeseries(
        metric=metric,
        days=days,
        interval=interval,
        crop_type=crop_type
    )
    
    return TimeSeriesData(
        metric=metric,
        interval=interval,
        data=data,
        metadata={
            "start_date": (datetime.utcnow() - timedelta(days=days)).isoformat(),
            "end_date": datetime.utcnow().isoformat(),
            "total_points": len(data)
        }
    )

@router.get("/disease-distribution")
async def get_disease_distribution(
    days: int = Query(30, ge=1, le=365),
    crop_type: Optional[str] = None,
    limit: int = Query(10, ge=1, le=50),
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """Get disease distribution statistics"""
    user = await verify_token(credentials.credentials)
    
    distribution = await analytics_engine.get_disease_distribution(
        days=days,
        crop_type=crop_type,
        limit=limit
    )
    
    return distribution

@router.get("/performance-metrics")
async def get_performance_metrics(
    time_range: str = Query("24h", pattern="^(1h|24h|7d|30d)$"),
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """Get system performance metrics"""
    user = await verify_token(credentials.credentials)
    
    metrics = await analytics_engine.get_performance_metrics(time_range)
    return PerformanceMetrics(**metrics)

@router.get("/user-activity")
async def get_user_activity(
    days: int = Query(7, ge=1, le=90),
    activity_type: Optional[str] = Query(None, pattern="^(scan|prediction|login)$"),
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """Get user activity metrics"""
    user = await verify_token(credentials.credentials)
    
    activity = await metrics_service.get_user_activity(
        days=days,
        activity_type=activity_type
    )
    
    return UserActivityMetrics(**activity)

@router.get("/realtime")
async def get_realtime_metrics(
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """Get real-time platform metrics"""
    user = await verify_token(credentials.credentials)
    
    realtime_data = await metrics_service.get_realtime_metrics()
    return realtime_data

@router.get("/geospatial")
async def get_geospatial_analytics(
    days: int = Query(30, ge=1, le=365),
    crop_type: Optional[str] = None,
    disease_type: Optional[str] = None,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """Get geospatial distribution of diseases"""
    user = await verify_token(credentials.credentials)
    
    geo_data = await analytics_engine.get_geospatial_analytics(
        days=days,
        crop_type=crop_type,
        disease_type=disease_type
    )
    
    return geo_data
