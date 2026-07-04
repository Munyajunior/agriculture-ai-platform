# services/api-gateway/app/middleware/auth.py
"""Authentication middleware for API Gateway"""

from fastapi import Request, HTTPException, status
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response
from typing import Optional, Set
import jwt
from ..config import settings
from ..core.redis_client import redis_client


class AuthMiddleware(BaseHTTPMiddleware):
    """JWT authentication middleware for protected routes"""
    
    # Public routes that don't require authentication
    PUBLIC_PATHS: Set[str] = {
        "/",
        "/health",
        "/ready",
        "/metrics",
        "/api/docs",
        "/api/redoc",
        "/api/openapi.json",
        "/api/v1/auth/register",
        "/api/v1/auth/login",
        "/api/v1/auth/refresh",
        "/api/v1/auth/forgot-password",
        "/api/v1/auth/reset-password",
    }
    
    # Path prefixes that are public
    PUBLIC_PREFIXES: Set[str] = {
        "/static",
        "/assets",
    }
    
    async def dispatch(self, request: Request, call_next):
        # Check if route is public
        if self._is_public_path(request.url.path):
            return await call_next(request)
        
        # Extract token
        token = self._extract_token(request)
        if not token:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Missing authentication token",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        # Verify token
        payload = await self._verify_token(token)
        if not payload:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired token",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        # Check if token is blacklisted
        if await self._is_token_blacklisted(token):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token has been revoked",
            )
        
        # Attach user info to request state
        request.state.user_id = payload.get("sub")
        request.state.username = payload.get("username")
        request.state.user_role = payload.get("role")
        request.state.token = token
        
        # Check role-based access for specific endpoints
        if not await self._check_role_access(request, payload.get("role")):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions",
            )
        
        return await call_next(request)
    
    def _is_public_path(self, path: str) -> bool:
        """Check if path is publicly accessible"""
        if path in self.PUBLIC_PATHS:
            return True
        
        for prefix in self.PUBLIC_PREFIXES:
            if path.startswith(prefix):
                return True
        
        return False
    
    def _extract_token(self, request: Request) -> Optional[str]:
        """Extract JWT token from Authorization header"""
        auth_header = request.headers.get("Authorization")
        if not auth_header:
            # Also check cookie for token
            token = request.cookies.get("access_token")
            if token:
                return token
            return None
        
        parts = auth_header.split()
        if len(parts) != 2 or parts[0].lower() != "bearer":
            return None
        
        return parts[1]
    
    async def _verify_token(self, token: str) -> Optional[dict]:
        """Verify JWT token and return payload"""
        try:
            payload = jwt.decode(
                token,
                settings.SECRET_KEY,
                algorithms=[settings.ALGORITHM]
            )
            return payload
        except jwt.ExpiredSignatureError:
            return None
        except jwt.InvalidTokenError:
            return None
    
    async def _is_token_blacklisted(self, token: str) -> bool:
        """Check if token is blacklisted in Redis"""
        try:
            is_blacklisted = await redis_client.get(f"blacklist:{token}")
            return is_blacklisted is not None
        except:
            return False
    
    async def _check_role_access(self, request: Request, role: str) -> bool:
        """Check if user role has access to endpoint"""
        # Define role-based access rules
        admin_only_prefixes = ["/api/v1/admin", "/api/v1/users"]
        agronomist_prefixes = ["/api/v1/analytics", "/api/v1/verification"]
        
        path = request.url.path
        
        for prefix in admin_only_prefixes:
            if path.startswith(prefix) and role != "admin":
                return False
        
        for prefix in agronomist_prefixes:
            if path.startswith(prefix) and role not in ["admin", "agronomist"]:
                return False
        
        return True
