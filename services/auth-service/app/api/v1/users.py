# services/auth-service/app/api/v1/users.py
"""User management API endpoints"""

from uuid import UUID
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from ...core.database import get_db
from ...core.security import security_manager
from ...models.user import User
from ...schemas.auth import UserResponse, UserUpdate, ChangePasswordRequest
from ..dependencies import get_current_user, get_current_active_user, require_role

router = APIRouter()


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(
    current_user: User = Depends(get_current_user)
):
    """Get current user information"""
    return current_user


@router.put("/me", response_model=UserResponse)
async def update_current_user(
    user_update: UserUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Update current user information"""
    if user_update.full_name is not None:
        current_user.full_name = user_update.full_name
    if user_update.phone_number is not None:
        current_user.phone_number = user_update.phone_number
    if user_update.profile_picture_url is not None:
        current_user.profile_picture_url = user_update.profile_picture_url
    if user_update.preferences is not None:
        current_user.preferences = user_update.preferences
    
    await db.commit()
    await db.refresh(current_user)
    
    return current_user


@router.post("/me/change-password")
async def change_password(
    password_data: ChangePasswordRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Change current user's password"""
    # Verify current password
    if not security_manager.verify_password(password_data.current_password, current_user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Current password is incorrect"
        )
    
    # Update password
    current_user.hashed_password = security_manager.get_password_hash(password_data.new_password)
    current_user.password_changed_at = datetime.now(timezone.utc)
    
    await db.commit()
    
    return {"message": "Password successfully changed"}


@router.get("/{user_id}", response_model=UserResponse)
@require_role(["admin", "agronomist"])
async def get_user(
    user_id: UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Get user by ID (admin/agronomist only)"""
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    return user


@router.put("/{user_id}/role")
@require_role(["admin"])
async def update_user_role(
    user_id: UUID,
    role: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Update user role (admin only)"""
    if role not in ["farmer", "agronomist", "admin", "researcher"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid role"
        )
    
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    user.role = role
    await db.commit()
    
    return {"message": f"User role updated to {role}"}


@router.delete("/{user_id}")
@require_role(["admin"])
async def delete_user(
    user_id: UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Delete user (admin only)"""
    if user_id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete your own account"
        )
    
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    await db.delete(user)
    await db.commit()
    
    return {"message": "User deleted successfully"}
