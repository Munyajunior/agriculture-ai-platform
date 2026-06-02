# services/api-gateway/app/clients/auth_service.py
"""Auth service client"""

from typing import Optional, Dict, Any, List
import httpx
from ..config import settings
import logging

logger = logging.getLogger(__name__)


class AuthServiceClient:
    """Client for Auth Service communication"""
    
    def __init__(self):
        self.base_url = settings.AUTH_SERVICE_URL
        self.timeout = 30.0
    
    async def _request(
        self,
        method: str,
        endpoint: str,
        data: Optional[Dict] = None,
        token: Optional[str] = None
    ) -> Dict[str, Any]:
        """Make HTTP request to auth service"""
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            headers = {}
            if token:
                headers["Authorization"] = f"Bearer {token}"
            
            url = f"{self.base_url}{endpoint}"
            
            try:
                if method == "GET":
                    response = await client.get(url, headers=headers, params=data)
                elif method == "POST":
                    response = await client.post(url, headers=headers, json=data)
                elif method == "PUT":
                    response = await client.put(url, headers=headers, json=data)
                elif method == "DELETE":
                    response = await client.delete(url, headers=headers)
                else:
                    raise ValueError(f"Unsupported method: {method}")
                
                response.raise_for_status()
                return response.json()
                
            except httpx.HTTPStatusError as e:
                logger.error(f"Auth service error: {e.response.text}")
                raise
            except Exception as e:
                logger.error(f"Auth service request failed: {e}")
                raise
    
    async def get_user_by_id(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Get user by ID"""
        try:
            return await self._request("GET", f"/users/{user_id}")
        except:
            return None
    
    async def get_user_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        """Get user by email"""
        try:
            return await self._request("GET", "/users", data={"email": email})
        except:
            return None
    
    async def verify_token(self, token: str) -> Optional[Dict[str, Any]]:
        """Verify JWT token with auth service"""
        try:
            return await self._request("POST", "/verify", token=token)
        except:
            return None
    
    async def refresh_token(self, refresh_token: str) -> Dict[str, Any]:
        """Refresh access token"""
        return await self._request("POST", "/refresh", data={"refresh_token": refresh_token})
    
    async def logout(self, token: str) -> bool:
        """Logout user and invalidate token"""
        try:
            await self._request("POST", "/logout", token=token)
            return True
        except:
            return False