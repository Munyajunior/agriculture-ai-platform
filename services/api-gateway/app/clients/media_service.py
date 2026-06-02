# services/api-gateway/app/clients/media_service.py
"""Media service client"""

from typing import Optional, Dict, Any
from uuid import UUID
from fastapi import UploadFile
import httpx
from ..config import settings
import logging

logger = logging.getLogger(__name__)


class MediaServiceClient:
    """Client for Media Service communication"""
    
    def __init__(self):
        self.base_url = settings.MEDIA_SERVICE_URL
        self.timeout = 120.0  # Longer timeout for file uploads
    
    async def upload_image(
        self,
        file: UploadFile,
        user_id: UUID,
        farm_id: Optional[UUID] = None
    ) -> str:
        """Upload image to media service"""
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            url = f"{self.base_url}/api/v1/media/upload"
            
            # Prepare form data
            files = {
                "file": (file.filename, await file.read(), file.content_type)
            }
            
            data = {
                "user_id": str(user_id),
                "farm_id": str(farm_id) if farm_id else None
            }
            
            try:
                response = await client.post(url, files=files, data=data)
                response.raise_for_status()
                result = response.json()
                return result["image_url"]
                
            except Exception as e:
                logger.error(f"Media service upload failed: {e}")
                raise
    
    async def download_image(self, image_url: str) -> bytes:
        """Download image from URL"""
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                response = await client.get(image_url)
                response.raise_for_status()
                return response.content
                
            except Exception as e:
                logger.error(f"Failed to download image: {e}")
                raise
    
    async def get_image_metadata(self, image_id: str) -> Dict[str, Any]:
        """Get image metadata"""
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            url = f"{self.base_url}/api/v1/media/{image_id}"
            
            try:
                response = await client.get(url)
                response.raise_for_status()
                return response.json()
                
            except Exception as e:
                logger.error(f"Failed to get image metadata: {e}")
                raise
    
    async def delete_image(self, image_id: str) -> bool:
        """Delete image from storage"""
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            url = f"{self.base_url}/api/v1/media/{image_id}"
            
            try:
                response = await client.delete(url)
                response.raise_for_status()
                return True
                
            except Exception as e:
                logger.error(f"Failed to delete image: {e}")
                return False
    
    async def generate_thumbnail(self, image_url: str, size: tuple = (300, 300)) -> str:
        """Generate thumbnail for image"""
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            url = f"{self.base_url}/api/v1/media/thumbnail"
            
            data = {
                "image_url": image_url,
                "width": size[0],
                "height": size[1]
            }
            
            try:
                response = await client.post(url, json=data)
                response.raise_for_status()
                result = response.json()
                return result["thumbnail_url"]
                
            except Exception as e:
                logger.error(f"Failed to generate thumbnail: {e}")
                return image_url