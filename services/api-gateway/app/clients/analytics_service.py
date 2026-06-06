# services/api-gateway/app/clients/analytics_service.py
"""Analytics service client"""

from typing import Optional, Dict, Any, List
from datetime import datetime, timezone
from ..config import settings
from .base import BaseServiceClient


class AnalyticsServiceClient(BaseServiceClient):
    """Client for Analytics Service communication"""
    
    def __init__(self):
        super().__init__(settings.ANALYTICS_SERVICE_URL, timeout=30.0)
        self.service_name = "Analytics service"
    
    async def get_dashboard_stats(
        self,
        start_date: datetime,
        end_date: datetime,
        crop_type: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get dashboard statistics"""
        data = {
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "crop_type": crop_type
        }
        
        return await self._request("GET", "/api/v1/analytics/dashboard", data=data)
    
    async def get_disease_distribution(
        self,
        start_date: datetime,
        end_date: datetime
    ) -> Dict[str, Any]:
        """Get disease distribution analytics"""
        data = {
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat()
        }
        
        return await self._request("GET", "/api/v1/analytics/diseases", data=data)
    
    async def get_user_engagement(
        self,
        start_date: datetime,
        end_date: datetime
    ) -> Dict[str, Any]:
        """Get user engagement metrics"""
        data = {
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat()
        }
        
        return await self._request("GET", "/api/v1/analytics/engagement", data=data)
    
    async def get_performance_metrics(
        self,
        start_date: datetime,
        end_date: datetime
    ) -> Dict[str, Any]:
        """Get system performance metrics"""
        data = {
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat()
        }
        
        return await self._request("GET", "/api/v1/analytics/performance", data=data)
    
    async def track_event(
        self,
        event_type: str,
        user_id: Optional[str] = None,
        metadata: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """Track custom analytics event"""
        data = {
            "event_type": event_type,
            "user_id": user_id,
            "metadata": metadata or {},
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
        return await self._request("POST", "/api/v1/analytics/track", data=data)
