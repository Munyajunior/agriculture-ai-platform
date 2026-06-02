# services/auth-service/app/api/v1/api_keys.py
"""API key management endpoints"""

from datetime import datetime, timedelta
from typing import Optional, List
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_

from ...core.database import get_db
from ...core.security import security_manager
from ...models.user import User, APIKey
from ...schemas.auth import APIKeyCreate, APIKeyResponse
from ..dependencies import get_current_user, get_current_active_user, require_role

router = APIRouter()


@router.get("/", response_model=list[APIKeyResponse])
async def list_api_keys(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """List all API keys for current user"""
    result = await db.execute(
        select(APIKey).where(APIKey.user_id == current_user.id)
    )
    keys = result.scalars().all()
    
    return keys


@router.post("/", response_model=APIKeyResponse, status_code=status.HTTP_201_CREATED)
async def create_api_key(
    key_data: APIKeyCreate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Create a new API key"""
    # Generate API key
    api_key, hashed_key = security_manager.generate_api_key()
    
    # Set expiration
    expires_at = None
    if key_data.expires_in_days:
        expires_at = datetime.utcnow() + timedelta(days=key_data.expires_in_days)
    
    # Create API key record
    api_key_obj = APIKey(
        user_id=current_user.id,
        name=key_data.name,
        key_hash=hashed_key,
        expires_at=expires_at,
        permissions=key_data.permissions,
        is_active=True
    )
    
    db.add(api_key_obj)
    await db.commit()
    await db.refresh(api_key_obj)
    
    # Return key (only time it's shown)
    return {
        "id": api_key_obj.id,
        "name": api_key_obj.name,
        "key": api_key,  # Only returned once
        "last_used_at": api_key_obj.last_used_at,
        "expires_at": api_key_obj.expires_at,
        "is_active": api_key_obj.is_active,
        "created_at": api_key_obj.created_at
    }


@router.put("/{key_id}/rotate", response_model=APIKeyResponse)
async def rotate_api_key(
    key_id: UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Rotate (regenerate) an API key"""
    # Get existing key
    result = await db.execute(
        select(APIKey).where(
            and_(
                APIKey.id == key_id,
                APIKey.user_id == current_user.id
            )
        )
    )
    api_key_obj = result.scalar_one_or_none()
    
    if not api_key_obj:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="API key not found"
        )
    
    # Generate new key
    new_key, new_hashed = security_manager.generate_api_key()
    
    # Update record
    api_key_obj.key_hash = new_hashed
    api_key_obj.last_used_at = None
    
    await db.commit()
    await db.refresh(api_key_obj)
    
    return {
        "id": api_key_obj.id,
        "name": api_key_obj.name,
        "key": new_key,
        "last_used_at": api_key_obj.last_used_at,
        "expires_at": api_key_obj.expires_at,
        "is_active": api_key_obj.is_active,
        "created_at": api_key_obj.created_at
    }


@router.patch("/{key_id}/toggle")
async def toggle_api_key(
    key_id: UUID,
    is_active: bool,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Enable or disable an API key"""
    result = await db.execute(
        select(APIKey).where(
            and_(
                APIKey.id == key_id,
                APIKey.user_id == current_user.id
            )
        )
    )
    api_key_obj = result.scalar_one_or_none()
    
    if not api_key_obj:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="API key not found"
        )
    
    api_key_obj.is_active = is_active
    await db.commit()
    
    return {
        "message": f"API key {'enabled' if is_active else 'disabled'} successfully",
        "is_active": is_active
    }


@router.delete("/{key_id}")
async def delete_api_key(
    key_id: UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Delete an API key"""
    result = await db.execute(
        select(APIKey).where(
            and_(
                APIKey.id == key_id,
                APIKey.user_id == current_user.id
            )
        )
    )
    api_key_obj = result.scalar_one_or_none()
    
    if not api_key_obj:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="API key not found"
        )
    
    await db.delete(api_key_obj)
    await db.commit()
    
    return {"message": "API key deleted successfully"}


@router.get("/admin/keys")
@require_role(["admin"])
async def list_all_api_keys(
    user_id: Optional[UUID] = None,
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db)
):
    """Admin: List all API keys across users"""
    query = select(APIKey)
    
    if user_id:
        query = query.where(APIKey.user_id == user_id)
    
    query = query.offset(skip).limit(limit)
    result = await db.execute(query)
    keys = result.scalars().all()
    
    # Get user info for each key
    response = []
    for key in keys:
        user = await db.get(User, key.user_id)
        response.append({
            "id": key.id,
            "name": key.name,
            "user": {
                "id": user.id,
                "username": user.username,
                "email": user.email
            },
            "last_used_at": key.last_used_at,
            "expires_at": key.expires_at,
            "is_active": key.is_active,
            "created_at": key.created_at
        })
    
    return response


# API Key authentication dependency for external services
async def verify_api_key(
    request: Request,
    db: AsyncSession = Depends(get_db)
) -> User:
    """Verify API key from X-API-Key header"""
    api_key = request.headers.get("X-API-Key")
    
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API key required"
        )
    
    # Hash the provided key
    hashed_key = security_manager.hash_api_key(api_key)
    
    # Find matching API key
    result = await db.execute(
        select(APIKey).where(
            and_(
                APIKey.key_hash == hashed_key,
                APIKey.is_active == True
            )
        )
    )
    api_key_obj = result.scalar_one_or_none()
    
    if not api_key_obj:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key"
        )
    
    # Check expiration
    if api_key_obj.expires_at and api_key_obj.expires_at < datetime.utcnow():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API key expired"
        )
    
    # Update last used timestamp
    api_key_obj.last_used_at = datetime.utcnow()
    await db.commit()
    
    # Get user
    user = await db.get(User, api_key_obj.user_id)
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account not active"
        )
    
    return user