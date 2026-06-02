# services/api-gateway/app/schemas/analytics.py
"""Analytics schemas"""

from typing import Optional, Dict, List, Any
from datetime import datetime
from pydantic import BaseModel, Field


class AnalyticsQuery(BaseModel):
    """Analytics query parameters"""
    start_date: datetime
    end_date: datetime
    crop_type: Optional[str] = None
    disease_type: Optional[str] = None
    group_by: str = "day"  # hour, day, week, month


class DashboardStats(BaseModel):
    """Dashboard statistics"""
    total_users: int
    active_users_7d: int
    total_scans: int
    scans_24h: int
    total_predictions: int
    avg_confidence: float
    edge_vs_cloud_ratio: Dict[str, float]
    most_common_diseases: List[Dict[str, Any]]
    recent_activity: List[Dict[str, Any]]


class DiseaseDistribution(BaseModel):
    """Disease distribution analytics"""
    disease_name: str
    count: int
    percentage: float
    avg_confidence: float


class UserEngagementMetrics(BaseModel):
    """User engagement metrics"""
    daily_active_users: List[Dict[str, Any]]
    weekly_active_users: List[Dict[str, Any]]
    retention_rate: float
    avg_sessions_per_user: float


class PerformanceMetrics(BaseModel):
    """System performance metrics"""
    avg_inference_time_ms: float
    p95_inference_time_ms: float
    p99_inference_time_ms: float
    success_rate: float
    cloud_vs_edge_comparison: Dict[str, float]


class AnalyticsResponse(BaseModel):
    """Analytics response"""
    query: AnalyticsQuery
    dashboard: Optional[DashboardStats] = None
    disease_distribution: Optional[List[DiseaseDistribution]] = None
    user_engagement: Optional[UserEngagementMetrics] = None
    performance: Optional[PerformanceMetrics] = None
    timeline_data: List[Dict[str, Any]]