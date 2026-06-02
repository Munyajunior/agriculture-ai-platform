# services/api-gateway/app/core/dependencies.py
"""Dependency injection for API Gateway"""

from typing import Optional, Dict, Any
from fastapi import Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import jwt
from ..config import settings
from ..clients.auth_service import AuthServiceClient
from ..core.redis_client import redis_client

security = HTTPBearer(auto_error=False)
auth_client = AuthServiceClient()


async def get_token_from_request(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)
) -> Optional[str]:
    """Extract token from request"""
    token = None
    
    # Check Authorization header
    if credentials:
        token = credentials.credentials
    
    # Check cookie
    if not token:
        token = request.cookies.get("access_token")
    
    return token


async def get_current_user(
    token: Optional[str] = Depends(get_token_from_request)
) -> Dict[str, Any]:
    """Get current authenticated user"""
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Check if token is blacklisted
    is_blacklisted = await redis_client.get(f"blacklist:{token}")
    if is_blacklisted:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has been revoked",
        )
    
    try:
        # Decode JWT
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM]
        )
        
        # Get user details from auth service
        user = await auth_client.get_user_by_id(payload.get("sub"))
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found",
            )
        
        return user
        
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
        )
    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
        )


async def get_current_active_user(
    current_user: Dict[str, Any] = Depends(get_current_user)
) -> Dict[str, Any]:
    """Get current active user"""
    if not current_user.get("is_active"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Inactive user"
        )
    
    if not current_user.get("is_verified"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Email not verified"
        )
    
    return current_user


async def get_current_admin_user(
    current_user: Dict[str, Any] = Depends(get_current_active_user)
) -> Dict[str, Any]:
    """Get current admin user"""
    if current_user.get("role") != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required"
        )
    
    return current_user


async def get_current_agronomist_user(
    current_user: Dict[str, Any] = Depends(get_current_active_user)
) -> Dict[str, Any]:
    """Get current agronomist or admin user"""
    if current_user.get("role") not in ["admin", "agronomist"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Agronomist or admin privileges required"
        )
    
    return current_user


async def get_current_farmer_user(
    current_user: Dict[str, Any] = Depends(get_current_active_user)
) -> Dict[str, Any]:
    """Get current farmer user"""
    if current_user.get("role") not in ["admin", "farmer"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Farmer or admin privileges required"
        )
    
    return current_user


def get_optional_user(
    token: Optional[str] = Depends(get_token_from_request)
) -> Optional[Dict[str, Any]]:
    """Get current user if authenticated, otherwise None"""
    if not token:
        return None
    
    try:
        return get_current_user(token)
    except HTTPException:
        return None