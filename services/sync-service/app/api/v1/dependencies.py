# services/sync-service/app/api/v1/dependencies.py
"""API dependencies for Sync Service"""

from fastapi import Depends, HTTPException, status, Header
from typing import Optional, Dict, Any
from uuid import UUID


async def verify_device(
    x_device_id: Optional[str] = Header(None),
    x_user_id: Optional[str] = Header(None)
) -> UUID:
    """Verify device authentication"""
    
    if not x_device_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="X-Device-ID header required"
        )
    
    if not x_user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="X-User-ID header required"
        )
    
    try:
        user_id = UUID(x_user_id)
        return user_id
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid X-User-ID format"
        )


async def verify_sync_token(
    sync_token: Optional[str] = Header(None)
) -> Optional[str]:
    """Verify sync token"""
    return sync_token