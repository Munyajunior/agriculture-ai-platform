# services/analytics-service/app/schemas/reports.py
"""Report schemas for API validation"""

from typing import List, Dict, Any, Optional
from datetime import datetime
from pydantic import BaseModel, Field


class ReportRequest(BaseModel):
    """Report generation request"""
    report_type: str = Field(..., regex="^(dashboard|disease|performance|export)$")
    parameters: Dict[str, Any] = Field(default_factory=dict)
    format: str = Field(default="pdf", regex="^(pdf|csv|excel|json)$")


class ReportResponse(BaseModel):
    """Report generation response"""
    task_id: str
    status: str
    estimated_time: int
    message: str


class ReportMetadata(BaseModel):
    """Report metadata"""
    id: str
    report_type: str
    generated_by: str
    generated_at: datetime
    file_size: int
    format: str
    parameters: Dict[str, Any]


class ScheduledReportRequest(BaseModel):
    """Schedule report request"""
    report_type: str
    parameters: Dict[str, Any]
    schedule: str = Field(..., regex="^(daily|weekly|monthly)$")
    recipients: List[str]