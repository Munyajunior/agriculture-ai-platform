# services/analytics-service/app/api/v1/diseases.py
"""Disease analytics endpoints"""

from typing import Optional, List
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from app.services.analytics_engine import analytics_engine
from app.core.auth import verify_token

router = APIRouter()
security = HTTPBearer()


@router.get("/statistics")
async def get_disease_statistics(
    days: int = Query(30, ge=1, le=365),
    crop_type: Optional[str] = None,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """Get disease statistics and distribution"""
    user = await verify_token(credentials.credentials)
    
    distribution = await analytics_engine.get_disease_distribution(
        days=days,
        crop_type=crop_type
    )
    
    return {
        "distribution": distribution,
        "total_diseases": len(distribution),
        "period_days": days
    }


@router.get("/trends/{disease_type}")
async def get_disease_trends(
    disease_type: str,
    days: int = Query(90, ge=1, le=365),
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """Get trends for specific disease"""
    user = await verify_token(credentials.credentials)
    
    trends = await analytics_engine.get_timeseries(
        metric="predictions",
        days=days,
        interval="day"
    )
    
    # Filter for specific disease
    filtered_trends = [
        t for t in trends 
        if t.get("disease_type") == disease_type
    ]
    
    return {
        "disease_type": disease_type,
        "trends": filtered_trends,
        "period_days": days
    }


@router.get("/comparison")
async def compare_diseases(
    diseases: List[str] = Query(...),
    days: int = Query(30, ge=1, le=365),
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """Compare multiple diseases"""
    user = await verify_token(credentials.credentials)
    
    comparison = {}
    for disease in diseases:
        distribution = await analytics_engine.get_disease_distribution(
            days=days
        )
        
        disease_data = next(
            (d for d in distribution if d["disease_type"] == disease),
            None
        )
        
        comparison[disease] = disease_data or {
            "count": 0,
            "percentage": 0,
            "avg_confidence": 0
        }
    
    return {
        "comparison": comparison,
        "period_days": days
    }


@router.get("/hotspots")
async def get_disease_hotspots(
    days: int = Query(7, ge=1, le=90),
    min_detections: int = Query(5, ge=1),
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """Get disease hotspots based on detection density"""
    user = await verify_token(credentials.credentials)
    
    hotspots = await analytics_engine.get_geospatial_analytics(
        days=days
    )
    
    # Filter by minimum detections
    filtered_hotspots = [
        h for h in hotspots.get("features", [])
        if h["properties"]["count"] >= min_detections
    ]
    
    return {
        "hotspots": filtered_hotspots,
        "total_hotspots": len(filtered_hotspots),
        "period_days": days,
        "min_detections": min_detections
    }