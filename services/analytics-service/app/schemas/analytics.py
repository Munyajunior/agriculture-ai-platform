# services/analytics-service/app/schemas/analytics.py
"""Analytics schemas for API validation"""

from typing import List, Dict, Any, Optional
from datetime import datetime
from pydantic import BaseModel, Field


class DashboardSummary(BaseModel):
    """Dashboard summary statistics"""
    total_scans: int
    total_predictions: int
    avg_confidence: float
    active_users: int
    inference_distribution: Dict[str, int]
    top_diseases: List[Dict[str, Any]]
    daily_trends: List[Dict[str, Any]]
    period_days: int
    start_date: str
    end_date: str


class TimeSeriesData(BaseModel):
    """Time series data response"""
    metric: str
    interval: str
    data: List[Dict[str, Any]]
    metadata: Dict[str, Any]


class DiseaseDistribution(BaseModel):
    """Disease distribution statistics"""
    disease_type: str
    count: int
    percentage: float
    avg_confidence: float
    severity: str


class PerformanceMetrics(BaseModel):
    """System performance metrics"""
    average_processing_time_ms: float
    success_rate: float
    confidence_distribution: Dict[str, int]
    inference_speed_by_source: Dict[str, float]
    time_range: str
    total_predictions: int


class UserActivityMetrics(BaseModel):
    """User activity metrics"""
    total_active_users: int
    new_users: int
    scans_per_user: float
    predictions_per_user: float
    top_users: List[Dict[str, Any]]
    activity_timeline: List[Dict[str, Any]]


class GeospatialFeature(BaseModel):
    """Geospatial feature"""
    type: str
    geometry: Dict[str, Any]
    properties: Dict[str, Any]


class GeospatialAnalytics(BaseModel):
    """Geospatial analytics response"""
    type: str = "FeatureCollection"
    features: List[GeospatialFeature]
    metadata: Dict[str, Any]


class PredictiveForecast(BaseModel):
    """Predictive analytics forecast"""
    forecast_values: List[float]
    forecast_dates: List[str]
    peak_days: List[int]
    trend: str
    high_risk_days: List[int]
    expected_total_cases: int
    max_expected_daily_cases: int
    model_confidence: float


class RiskAssessment(BaseModel):
    """Risk assessment response"""
    overall_risk_score: float
    risk_level: str
    regional_risk: Dict[str, Any]
    recommendations: List[str]
    factors: List[str]
    confidence: float