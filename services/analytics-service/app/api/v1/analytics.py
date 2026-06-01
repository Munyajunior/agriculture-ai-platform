# services/analytics-service/app/api/v1/analytics.py
"""Analytics API endpoints"""

from typing import Optional, Dict, Any
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, text

from app.core.database import get_db
from app.core.cache import cache_manager
from shared.types.agriculture_ai.types.schemas import (
    AnalyticsQuery, AnalyticsResponse, 
    DashboardMetrics, DiseaseTrend, GeoDistribution
)

router = APIRouter()


@router.get("/dashboard", response_model=DashboardMetrics)
async def get_dashboard_metrics(
    days: int = Query(30, ge=1, le=365),
    db: AsyncSession = Depends(get_db)
):
    """Get main dashboard metrics"""
    cache_key = f"dashboard_metrics_{days}"
    
    # Try cache first
    cached = await cache_manager.get(cache_key)
    if cached:
        return cached
    
    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=days)
    
    # Total scans
    total_scans_result = await db.execute(
        select(func.count()).select_from(Scan).where(
            Scan.created_at >= start_date
        )
    )
    total_scans = total_scans_result.scalar()
    
    # Total predictions
    total_predictions_result = await db.execute(
        select(func.count()).select_from(Prediction).where(
            Prediction.created_at >= start_date
        )
    )
    total_predictions = total_predictions_result.scalar()
    
    # Average confidence
    avg_confidence_result = await db.execute(
        select(func.avg(Prediction.confidence_score)).where(
            Prediction.created_at >= start_date
        )
    )
    avg_confidence = avg_confidence_result.scalar() or 0
    
    # Unique users
    unique_users_result = await db.execute(
        select(func.count(func.distinct(Scan.user_id))).where(
            Scan.created_at >= start_date
        )
    )
    unique_users = unique_users_result.scalar()
    
    # Inference source distribution
    inference_distribution_result = await db.execute(
        select(
            Prediction.inference_source, 
            func.count()
        ).where(
            Prediction.created_at >= start_date
        ).group_by(Prediction.inference_source)
    )
    inference_distribution = dict(inference_distribution_result.all())
    
    # Disease distribution (top 5)
    disease_distribution_result = await db.execute(
        select(
            Prediction.disease_type,
            func.count()
        ).where(
            Prediction.created_at >= start_date
        ).group_by(Prediction.disease_type)
        .order_by(func.count().desc())
        .limit(5)
    )
    disease_distribution = [
        {"disease": d, "count": c} 
        for d, c in disease_distribution_result.all()
    ]
    
    metrics = DashboardMetrics(
        total_scans=total_scans,
        total_predictions=total_predictions,
        average_confidence=avg_confidence,
        unique_users=unique_users,
        inference_source_distribution=inference_distribution,
        top_diseases=disease_distribution,
        period_days=days
    )
    
    # Cache for 5 minutes
    await cache_manager.set(cache_key, metrics, ttl=300)
    
    return metrics


@router.get("/diseases/trends", response_model=list[DiseaseTrend])
async def get_disease_trends(
    disease_type: Optional[str] = None,
    days: int = Query(30, ge=1, le=365),
    db: AsyncSession = Depends(get_db)
):
    """Get disease trends over time"""
    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=days)
    
    query = select(
        func.date_trunc('day', Prediction.created_at).label('date'),
        Prediction.disease_type,
        func.count().label('count')
    ).where(
        Prediction.created_at >= start_date
    ).group_by(
        func.date_trunc('day', Prediction.created_at),
        Prediction.disease_type
    ).order_by('date')
    
    if disease_type:
        query = query.where(Prediction.disease_type == disease_type)
    
    result = await db.execute(query)
    rows = result.all()
    
    # Group by date
    trends = {}
    for row in rows:
        date = row.date.isoformat()
        if date not in trends:
            trends[date] = {}
        trends[date][row.disease_type] = row.count
    
    return [
        DiseaseTrend(date=date, diseases=trends[date])
        for date in sorted(trends.keys())
    ]


@router.get("/geo/distribution", response_model=list[GeoDistribution])
async def get_geo_distribution(
    days: int = Query(30, ge=1, le=365),
    db: AsyncSession = Depends(get_db)
):
    """Get geographic distribution of predictions"""
    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=days)
    
    # Aggregate by country/region (using location data from scans)
    result = await db.execute(
        select(
            Scan.location_country,
            Scan.location_region,
            func.count(Scan.id).label('scan_count'),
            func.avg(Prediction.confidence_score).label('avg_confidence')
        ).join(
            Prediction, Prediction.scan_id == Scan.id
        ).where(
            Scan.created_at >= start_date,
            Scan.location_country.isnot(None)
        ).group_by(
            Scan.location_country,
            Scan.location_region
        ).order_by(func.count(Scan.id).desc())
        .limit(20)
    )
    
    rows = result.all()
    
    return [
        GeoDistribution(
            country=row.location_country,
            region=row.location_region,
            scan_count=row.scan_count,
            average_confidence=row.avg_confidence or 0
        )
        for row in rows
    ]


@router.get("/performance/model")
async def get_model_performance(
    model_version: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
):
    """Get model performance metrics"""
    query = select(ModelVersion)
    
    if model_version:
        query = query.where(ModelVersion.version == model_version)
    else:
        query = query.where(ModelVersion.is_active == True)
    
    result = await db.execute(query)
    models = result.scalars().all()
    
    return [
        {
            "version": m.version,
            "accuracy": m.accuracy,
            "precision": m.precision,
            "recall": m.recall,
            "f1_score": m.f1_score,
            "model_size_mb": m.model_size_mb,
            "inference_time_avg": await _get_avg_inference_time(m.id, db),
            "total_predictions": await _get_total_predictions(m.id, db)
        }
        for m in models
    ]


async def _get_avg_inference_time(model_id, db) -> float:
    """Get average inference time for model"""
    result = await db.execute(
        select(func.avg(Prediction.processing_time_ms))
        .where(Prediction.model_version_id == model_id)
    )
    return result.scalar() or 0


async def _get_total_predictions(model_id, db) -> int:
    """Get total predictions made by model"""
    result = await db.execute(
        select(func.count()).select_from(Prediction)
        .where(Prediction.model_version_id == model_id)
    )
    return result.scalar() or 0