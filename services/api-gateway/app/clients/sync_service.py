# services/api-gateway/app/clients/sync_service.py
"""Sync service client"""

from typing import Optional, Dict, Any, List
from uuid import UUID
import httpx
from ..config import settings
import logging

logger = logging.getLogger(__name__)


class SyncServiceClient:
    """Client for Sync Service communication"""
    
    def __init__(self):
        self.base_url = settings.SYNC_SERVICE_URL
        self.timeout = 60.0
    
    async def _request(
        self,
        method: str,
        endpoint: str,
        data: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """Make HTTP request to sync service"""
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            url = f"{self.base_url}{endpoint}"
            
            try:
                if method == "POST":
                    response = await client.post(url, json=data)
                elif method == "GET":
                    response = await client.get(url, params=data)
                else:
                    raise ValueError(f"Unsupported method: {method}")
                
                response.raise_for_status()
                return response.json()
                
            except httpx.HTTPStatusError as e:
                logger.error(f"Sync service error: {e.response.text}")
                raise
            except Exception as e:
                logger.error(f"Sync service request failed: {e}")
                raise
    
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