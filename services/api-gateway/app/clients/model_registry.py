# services/api-gateway/app/clients/model_registry.py
"""Model registry client"""

from typing import Optional, Dict, Any, List
import httpx
from ..config import settings
import logging

logger = logging.getLogger(__name__)


class ModelRegistryClient:
    """Client for Model Registry Service communication"""
    
    def __init__(self):
        self.base_url = settings.MODEL_REGISTRY_URL
        self.timeout = 30.0
    
    async def _request(
        self,
        method: str,
        endpoint: str,
        data: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """Make HTTP request to model registry"""
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            url = f"{self.base_url}{endpoint}"
            
            try:
                if method == "GET":
                    response = await client.get(url, params=data)
                elif method == "POST":
                    response = await client.post(url, json=data)
                elif method == "PUT":
                    response = await client.put(url, json=data)
                else:
                    raise ValueError(f"Unsupported method: {method}")
                
                response.raise_for_status()
                return response.json()
                
            except httpx.HTTPStatusError as e:
                logger.error(f"Model registry error: {e.response.text}")
                raise
            except Exception as e:
                logger.error(f"Model registry request failed: {e}")
                raise
    
    async def get_active_model(self) -> Dict[str, Any]:
        """Get currently active model"""
        return await self._request("GET", "/api/v1/models/active")
    
    async def get_model_by_version(self, version: str) -> Dict[str, Any]:
        """Get model by version"""
        return await self._request("GET", f"/api/v1/models/{version}")
    
    async def get_model_download_url(self, model_id: str, format: str = "onnx") -> str:
        """Get download URL for model"""
        result = await self._request("GET", f"/api/v1/models/{model_id}/download", data={"format": format})
        return result.get("download_url")
    
    async def list_models(
        self,
        limit: int = 50,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """List available models"""
        result = await self._request("GET", "/api/v1/models", data={"limit": limit, "offset": offset})
        return result.get("models", [])
    
    async def register_model(
        self,
        name: str,
        version: str,
        model_url: str,
        metadata: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """Register new model"""
        data = {
            "name": name,
            "version": version,
            "model_url": model_url,
            "metadata": metadata or {}
        }
        
        return await self._request("POST", "/api/v1/models/register", data=data)
    
    async def set_active_model(self, model_id: str) -> Dict[str, Any]:
        """Set active model"""
        return await self._request("PUT", f"/api/v1/models/{model_id}/activate")
    
    async def get_model_metrics(self, model_id: str) -> Dict[str, Any]:
        """Get model performance metrics"""
        return await self._request("GET", f"/api/v1/models/{model_id}/metrics")