# services/api-gateway/app/clients/ai_service.py
"""AI service client"""

from typing import Optional, Dict, Any, List
from uuid import UUID
import httpx
from ..config import settings
import logging

logger = logging.getLogger(__name__)


class AIServiceClient:
    """Client for AI Service communication"""
    
    def __init__(self):
        self.base_url = settings.AI_SERVICE_URL
        self.timeout = 60.0  # Longer timeout for AI inference
    
    async def _request(
        self,
        method: str,
        endpoint: str,
        data: Optional[Dict] = None,
        files: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """Make HTTP request to AI service"""
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            url = f"{self.base_url}{endpoint}"
            
            try:
                if method == "POST":
                    if files:
                        response = await client.post(url, files=files, data=data)
                    else:
                        response = await client.post(url, json=data)
                elif method == "GET":
                    response = await client.get(url, params=data)
                else:
                    raise ValueError(f"Unsupported method: {method}")
                
                response.raise_for_status()
                return response.json()
                
            except httpx.HTTPStatusError as e:
                logger.error(f"AI service error: {e.response.text}")
                raise
            except Exception as e:
                logger.error(f"AI service request failed: {e}")
                raise
    
    async def cloud_inference(
        self,
        image_data: Optional[str] = None,
        image_url: Optional[str] = None,
        user_id: Optional[UUID] = None,
        farm_id: Optional[UUID] = None,
        device_type: str = "mobile",
        location_lat: Optional[float] = None,
        location_lon: Optional[float] = None
    ) -> Dict[str, Any]:
        """Perform cloud-based inference"""
        data = {
            "user_id": str(user_id) if user_id else None,
            "farm_id": str(farm_id) if farm_id else None,
            "device_type": device_type,
            "location_lat": location_lat,
            "location_lon": location_lon
        }
        
        if image_data:
            data["image_base64"] = image_data
        elif image_url:
            data["image_url"] = image_url
        
        return await self._request("POST", "/api/v1/inference/cloud", data=data)
    
    async def edge_inference(
        self,
        image_data: str,
        model_version: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get edge inference instructions"""
        data = {
            "image_base64": image_data,
            "model_version": model_version
        }
        
        return await self._request("POST", "/api/v1/inference/edge/prepare", data=data)
    
    async def batch_inference(
        self,
        images: List[str],
        user_id: Optional[UUID] = None,
        farm_id: Optional[UUID] = None
    ) -> List[Dict[str, Any]]:
        """Perform batch inference"""
        data = {
            "images": images,
            "user_id": str(user_id) if user_id else None,
            "farm_id": str(farm_id) if farm_id else None
        }
        
        result = await self._request("POST", "/api/v1/inference/batch", data=data)
        return result.get("predictions", [])
    
    async def get_prediction_history(
        self,
        user_id: UUID,
        limit: int = 50,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """Get prediction history for user"""
        params = {
            "user_id": str(user_id),
            "limit": limit,
            "offset": offset
        }
        
        result = await self._request("GET", "/api/v1/predictions/history", data=params)
        return result.get("predictions", [])
    
    async def get_prediction_details(self, prediction_id: UUID) -> Dict[str, Any]:
        """Get detailed prediction information"""
        return await self._request("GET", f"/api/v1/predictions/{prediction_id}")
    
    async def get_model_info(self) -> Dict[str, Any]:
        """Get current model information"""
        return await self._request("GET", "/api/v1/model/info")
    
    async def prepare_edge_inference(self, image_data: str, request: Any) -> Dict[str, Any]:
        """Prepare data for edge inference"""
        return await self.edge_inference(image_data)