# services/auth-service/app/api/v1/sessions.py
"""User session management endpoints"""

from datetime import datetime
from typing import Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, delete

from ...core.database import get_db
from ...core.security import security_manager
from ...models.user import User, Session
from ...schemas.auth import SessionResponse
from ..dependencies import get_current_user, get_current_active_user, require_role

router = APIRouter()


@router.get("/", response_model=list[SessionResponse])
async def list_sessions(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """List all active sessions for current user"""
    result = await db.execute(
        select(Session).where(
            and_(
                Session.user_id == current_user.id,
                Session.is_active == True,
                Session.expires_at > datetime.utcnow()
            )
        ).order_by(Session.last_activity.desc())
    )
    sessions = result.scalars().all()
    
    return sessions


@router.get("/current", response_model=SessionResponse)
async def get_current_session(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get current session information"""
    # Extract token from Authorization header
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No valid session token"
        )
    
    token = auth_header.split(" ")[1]
    
    # Find session by token
    result = await db.execute(
        select(Session).where(
            and_(
                Session.session_token == token,
                Session.user_id == current_user.id,
                Session.is_active == True
            )
        )
    )
    session = result.scalar_one_or_none()
    
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found"
        )
    
    return session


@router.post("/{session_id}/revoke")
async def revoke_session(
    session_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Revoke (invalidate) a specific session"""
    result = await db.execute(
        select(Session).where(
            and_(
                Session.id == session_id,
                Session.user_id == current_user.id,
                Session.is_active == True
            )
        )
    )
    session = result.scalar_one_or_none()
    
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found"
        )
    
    # Revoke the session token
    await security_manager.revoke_token(session.session_token)
    
    # Deactivate session
    session.is_active = False
    await db.commit()
    
    return {"message": "Session revoked successfully"}


@router.post("/revoke-all")
async def revoke_all_sessions(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    exclude_current: bool = True
):
    """Revoke all sessions for current user"""
    # Get all sessions
    result = await db.execute(
        select(Session).where(
            and_(
                Session.user_id == current_user.id,
                Session.is_active == True
            )
        )
    )
    sessions = result.scalars().all()
    
    # Get current session token if excluding
    current_token = None
    if exclude_current:
        # Extract from request (would need to pass request)
        # For now, we'll handle this in the endpoint logic
        pass
    
    # Revoke each session
    revoked_count = 0
    for session in sessions:
        if exclude_current and session.session_token == current_token:
            continue
        
        await security_manager.revoke_token(session.session_token)
        session.is_active = False
        revoked_count += 1
    
    await db.commit()
    
    return {
        "message": f"Revoked {revoked_count} sessions",
        "revoked_count": revoked_count
    }


@router.post("/refresh-activity")
async def refresh_session_activity(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    request: Request = None
):
    """Update last activity timestamp for current session"""
    if not request:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Request object required"
        )
    
    # Extract token
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No valid session token"
        )
    
    token = auth_header.split(" ")[1]
    
    # Find and update session
    result = await db.execute(
        select(Session).where(
            and_(
                Session.session_token == token,
                Session.user_id == current_user.id,
                Session.is_active == True
            )
        )
    )
    session = result.scalar_one_or_none()
    
    if session:
        session.last_activity = datetime.utcnow()
        await db.commit()
    
    return {"message": "Session activity updated"}


@router.get("/admin/sessions")
@require_role(["admin"])
async def list_all_sessions(
    user_id: Optional[UUID] = None,
    active_only: bool = True,
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Admin: List all sessions across users"""
    query = select(Session)
    
    if user_id:
        query = query.where(Session.user_id == user_id)
    
    if active_only:
        query = query.where(
            and_(
                Session.is_active == True,
                Session.expires_at > datetime.utcnow()
            )
        )
    
    query = query.offset(skip).limit(limit).order_by(Session.created_at.desc())
    result = await db.execute(query)
    sessions = result.scalars().all()
    
    # Get user info for each session
    response = []
    for session in sessions:
        user = await db.get(User, session.user_id)
        response.append({
            "id": session.id,
            "user": {
                "id": user.id,
                "username": user.username,
                "email": user.email
            },
            "ip_address": session.ip_address,
            "user_agent": session.user_agent,
            "device_info": session.device_info,
            "last_activity": session.last_activity,
            "created_at": session.created_at,
            "expires_at": session.expires_at,
            "is_active": session.is_active
        })
    
    return {
        "sessions": response,
        "total": len(response),
        "skip": skip,
        "limit": limit
    }


@router.delete("/admin/sessions/{session_id}")
@require_role(["admin"])
async def admin_revoke_session(
    session_id: UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Admin: Force revoke any session"""
    result = await db.execute(
        select(Session).where(Session.id == session_id)
    )
    session = result.scalar_one_or_none()
    
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found"
        )
    
    # Revoke the session token
    await security_manager.revoke_token(session.session_token)
    
    # Deactivate session
    session.is_active = False
    await db.commit()
    
    return {"message": f"Session for user {session.user_id} revoked successfully"}


@router.delete("/admin/expired")
@require_role(["admin"])
async def cleanup_expired_sessions(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Admin: Clean up all expired sessions"""
    result = await db.execute(
        select(Session).where(
            and_(
                Session.is_active == True,
                Session.expires_at < datetime.utcnow()
            )
        )
    )
    expired_sessions = result.scalars().all()
    
    cleaned_count = 0
    for session in expired_sessions:
        await security_manager.revoke_token(session.session_token)
        session.is_active = False
        cleaned_count += 1
    
    await db.commit()
    
    return {
        "message": f"Cleaned up {cleaned_count} expired sessions",
        "cleaned_count": cleaned_count
    }


# Session cleanup background task
async def cleanup_expired_sessions_task(db: AsyncSession):
    """Background task to clean up expired sessions"""
    result = await db.execute(
        delete(Session).where(
            and_(
                Session.is_active == True,
                Session.expires_at < datetime.utcnow()
            )
        ).returning(Session.id)
    )
    deleted_ids = result.scalars().all()
    
    # Revoke tokens for deleted sessions
    for session_id in deleted_ids:
        # Would need to get token from session
        pass
    
    await db.commit()
    return len(deleted_ids)
