# services/api-gateway/app/clients/sync_service.py
"""Sync service client"""

from typing import Optional, Dict, Any, List
from uuid import UUID
from ..config import settings
from .base import BaseServiceClient


class SyncServiceClient(BaseServiceClient):
    """Client for Sync Service communication"""
    
    def __init__(self):
        super().__init__(settings.SYNC_SERVICE_URL, timeout=60.0)
        self.service_name = "Sync service"
    
    async def sync_offline_data(
        self,
        user_id: UUID,
        device_id: str,
        scans: List[Dict],
        predictions: List[Dict]
    ) -> Dict[str, Any]:
        """Sync offline data to cloud"""
        data = {
            "user_id": str(user_id),
            "device_id": device_id,
            "scans": scans,
            "predictions": predictions
        }
        
        return await self._request("POST", "/api/v1/sync/upload", data=data)
    
    async def get_pending_syncs(self, user_id: UUID) -> List[Dict]:
        """Get pending sync items for user"""
        result = await self._request("GET", "/api/v1/sync/pending", data={"user_id": str(user_id)})
        return result.get("pending_items", [])
    
    async def get_sync_status(self, sync_id: str) -> Dict[str, Any]:
        """Get sync status"""
        return await self._request("GET", f"/api/v1/sync/status/{sync_id}")
    
    async def get_offline_queue_stats(self, device_id: str) -> Dict[str, Any]:
        """Get offline queue statistics"""
        return await self._request("GET", "/api/v1/sync/queue/stats", data={"device_id": device_id})
