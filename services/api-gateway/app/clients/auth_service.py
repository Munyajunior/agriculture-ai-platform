# services/api-gateway/app/clients/auth_service.py
"""Auth service client"""

from typing import Optional, Dict, Any, List
from ..config import settings
from .base import BaseServiceClient


class AuthServiceClient(BaseServiceClient):
    """Client for Auth Service communication"""

    def __init__(self):
        super().__init__(settings.AUTH_SERVICE_URL, timeout=30.0)
        self.service_name = "Auth service"

    async def get_user_by_id(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Get user by ID"""
        try:
            return await self._request("GET", f"/api/v1/users/{user_id}")
        except Exception:
            return None

    async def get_user_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        """Get user by email"""
        try:
            return await self._request("GET", "/api/v1/users", data={"email": email})
        except Exception:
            return None

    async def verify_token(self, token: str) -> Optional[Dict[str, Any]]:
        """Verify JWT token with auth service"""
        try:
            return await self._request("GET", "/api/v1/users/me", token=token)
        except Exception:
            return None

    async def register_user(self, user_data: Dict[str, Any]) -> Dict[str, Any]:
        """Register a new user."""
        return await self._request("POST", "/api/v1/auth/register", data=user_data)

    async def login(self, login_data: Dict[str, Any]) -> Dict[str, Any]:
        """Authenticate a user."""
        return await self._request("POST", "/api/v1/auth/login", data=login_data)

    async def refresh_token(self, refresh_token: str) -> Dict[str, Any]:
        """Refresh access token"""
        return await self._request("POST", "/api/v1/auth/refresh", data={"refresh_token": refresh_token})

    async def change_password(self, token: str, password_data: Dict[str, Any]) -> Dict[str, Any]:
        """Change the current user's password."""
        return await self._request("POST", "/api/v1/users/me/change-password", data=password_data, token=token)

    async def update_current_user(self, token: str, user_update: Dict[str, Any]) -> Dict[str, Any]:
        """Update the current user's profile."""
        return await self._request("PUT", "/api/v1/users/me", data=user_update, token=token)

    async def forgot_password(self, email: str) -> Dict[str, Any]:
        """Request a password reset."""
        return await self._request("POST", "/api/v1/auth/forgot-password", data={"email": email})

    async def reset_password(self, token: str, new_password: str) -> Dict[str, Any]:
        """Reset password using a reset token."""
        return await self._request(
            "POST",
            "/api/v1/auth/reset-password",
            data={"token": token, "new_password": new_password},
        )

    async def logout(self, token: str) -> bool:
        """Logout user and invalidate token"""
        try:
            await self._request("POST", "/api/v1/auth/logout", token=token, data={"access_token": token})
            return True
        except Exception:
            return False
