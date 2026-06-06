# services/analytics-service/app/api/v1/reports.py
"""Report generation and management endpoints"""

from typing import Optional, Dict, Any
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Query
from fastapi.responses import FileResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from app.services.report_generator import ReportGenerator
from app.services.analytics_engine import analytics_engine
from app.core.auth import verify_token, require_role
from app.schemas.reports import (
    ReportRequest,
    ReportResponse,
    ReportMetadata,
    ScheduledReportRequest
)

router = APIRouter()
security = HTTPBearer()
report_generator = ReportGenerator()

@router.post("/generate")
async def generate_report(
    request: ReportRequest,
    background_tasks: BackgroundTasks,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """Generate analytics report"""
    user = await verify_token(credentials.credentials)
    
    # Validate user permissions
    if user.role not in ["admin", "agronomist", "researcher"]:
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    
    # Start report generation in background
    task_id = await report_generator.generate_async(
        report_type=request.report_type,
        parameters=request.parameters,
        user_id=user.id
    )
    
    return ReportResponse(
        task_id=task_id,
        status="processing",
        estimated_time=30,  # seconds
        message="Report generation started"
    )

@router.get("/status/{task_id}")
async def get_report_status(
    task_id: str,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """Get report generation status"""
    user = await verify_token(credentials.credentials)
    
    status = await report_generator.get_status(task_id)
    
    if not status:
        raise HTTPException(status_code=404, detail="Report task not found")
    
    return status

@router.get("/download/{task_id}")
async def download_report(
    task_id: str,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """Download generated report"""
    user = await verify_token(credentials.credentials)
    
    report_file = await report_generator.get_report_file(task_id)
    
    if not report_file:
        raise HTTPException(status_code=404, detail="Report not found or not ready")
    
    return FileResponse(
        path=report_file,
        filename=f"report_{task_id}.pdf",
        media_type="application/pdf"
    )

@router.get("/list")
async def list_reports(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    report_type: Optional[str] = None,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """List generated reports"""
    user = await verify_token(credentials.credentials)
    
    reports = await report_generator.list_reports(
        user_id=user.id,
        limit=limit,
        offset=offset,
        report_type=report_type
    )
    
    return {
        "reports": reports,
        "total": len(reports),
        "limit": limit,
        "offset": offset
    }

@router.delete("/{report_id}")
async def delete_report(
    report_id: str,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """Delete a generated report"""
    user = await verify_token(credentials.credentials)
    
    if user.role not in ["admin"]:
        raise HTTPException(status_code=403, detail="Admin access required")
    
    deleted = await report_generator.delete_report(report_id)
    
    if not deleted:
        raise HTTPException(status_code=404, detail="Report not found")
    
    return {"message": "Report deleted successfully"}

@router.post("/schedule")
async def schedule_report(
    request: ScheduledReportRequest,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """Schedule recurring report generation"""
    user = await verify_token(credentials.credentials)
    
    if user.role not in ["admin"]:
        raise HTTPException(status_code=403, detail="Admin access required")
    
    scheduled = await report_generator.schedule_report(
        report_type=request.report_type,
        parameters=request.parameters,
        schedule=request.schedule,
        recipients=request.recipients,
        user_id=user.id
    )
    
    return scheduled

@router.get("/export/dashboard")
async def export_dashboard_data(
    format: str = Query("csv", pattern="^(csv|json|excel)$"),
    days: int = Query(30, ge=1, le=365),
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """Export dashboard data in specified format"""
    user = await verify_token(credentials.credentials)
    
    export_data = await analytics_engine.export_dashboard_data(days=days)
    
    return await report_generator.export_data(export_data, format)
