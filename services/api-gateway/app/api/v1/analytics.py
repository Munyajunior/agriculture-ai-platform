# services/api-gateway/app/api/v1/analytics.py
"""Analytics API endpoints"""

from fastapi import APIRouter, Depends, HTTPException, Query
from datetime import datetime, timedelta
from typing import Optional

from ...schemas.analytics import AnalyticsQuery, AnalyticsResponse, DashboardStats
from ...clients.analytics_service import AnalyticsServiceClient
from ...core.dependencies import get_current_admin_user, get_current_agronomist_user

router = APIRouter()
analytics_client = AnalyticsServiceClient()


@router.get("/dashboard", response_model=DashboardStats)
async def get_dashboard_stats(
    days: int = Query(30, ge=1, le=365),
    current_user = Depends(get_current_agronomist_user)
):
    """Get dashboard statistics"""
    try:
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=days)
        
        stats = await analytics_client.get_dashboard_stats(
            start_date=start_date,
            end_date=end_date
        )
        
        return stats
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch dashboard stats: {str(e)}"
        )


@router.get("/diseases")
async def get_disease_analytics(
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    crop_type: Optional[str] = None,
    current_user = Depends(get_current_agronomist_user)
):
    """Get disease distribution analytics"""
    try:
        if not start_date:
            start_date = datetime.utcnow() - timedelta(days=30)
        if not end_date:
            end_date = datetime.utcnow()
        
        analytics = await analytics_client.get_disease_distribution(
            start_date=start_date,
            end_date=end_date
        )
        
        if crop_type:
            # Filter by crop type
            analytics["diseases"] = [
                d for d in analytics.get("diseases", [])
                if d.get("crop_type") == crop_type
            ]
        
        return analytics
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch disease analytics: {str(e)}"
        )


@router.get("/engagement")
async def get_user_engagement(
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    current_user = Depends(get_current_admin_user)
):
    """Get user engagement metrics"""
    try:
        if not start_date:
            start_date = datetime.utcnow() - timedelta(days=30)
        if not end_date:
            end_date = datetime.utcnow()
        
        metrics = await analytics_client.get_user_engagement(
            start_date=start_date,
            end_date=end_date
        )
        
        return metrics
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch engagement metrics: {str(e)}"
        )


@router.get("/performance")
async def get_performance_metrics(
    hours: int = Query(24, ge=1, le=168),
    current_user = Depends(get_current_admin_user)
):
    """Get system performance metrics"""
    try:
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(hours=hours)
        
        metrics = await analytics_client.get_performance_metrics(
            start_date=start_date,
            end_date=end_date
        )
        
        return metrics
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch performance metrics: {str(e)}"
        )


@router.get("/export")
async def export_analytics(
    format: str = Query("json", regex="^(json|csv)$"),
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    current_user = Depends(get_current_admin_user)
):
    """Export analytics data"""
    try:
        if not start_date:
            start_date = datetime.utcnow() - timedelta(days=30)
        if not end_date:
            end_date = datetime.utcnow()
        
        data = await analytics_client.get_dashboard_stats(start_date, end_date)
        
        if format == "csv":
            # Convert to CSV
            import csv
            from io import StringIO
            
            output = StringIO()
            writer = csv.DictWriter(output, fieldnames=data.keys())
            writer.writeheader()
            writer.writerow(data)
            
            return Response(
                content=output.getvalue(),
                media_type="text/csv",
                headers={"Content-Disposition": "attachment; filename=analytics.csv"}
            )
        else:
            return data
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to export analytics: {str(e)}"
        )