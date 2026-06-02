# services/auth-service/app/api/v1/auth.py
"""Authentication API endpoints"""

from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from ...core.database import get_db
from ...core.security import security_manager
from ...core.redis_client import redis_client
from ...models.user import User, Session
from ...schemas.auth import (
    LoginRequest, TokenResponse, RefreshTokenRequest,
    LogoutRequest, ForgotPasswordRequest, ResetPasswordRequest,
    VerifyEmailRequest, ResendVerificationRequest,
    UserResponse, UserCreate
)
from ...services.email_service import email_service

router = APIRouter()
security = HTTPBearer()


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(
    user_data: UserCreate,
    db: AsyncSession = Depends(get_db)
):
    """Register a new user"""
    # Check if user exists
    existing_user = await db.execute(
        select(User).where(
            (User.email == user_data.email) | (User.username == user_data.username)
        )
    )
    if existing_user.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User with this email or username already exists"
        )
    
    # Create new user
    hashed_password = security_manager.get_password_hash(user_data.password)
    new_user = User(
        email=user_data.email,
        username=user_data.username,
        hashed_password=hashed_password,
        full_name=user_data.full_name,
        phone_number=user_data.phone_number,
        role="farmer",
        is_verified=False,
        created_at=datetime.utcnow()
    )
    
    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)
    
    # Send verification email
    verification_token = await security_manager.generate_email_verification_token(new_user.id)
    await email_service.send_verification_email(new_user.email, verification_token)
    
    return new_user


@router.post("/login", response_model=TokenResponse)
async def login(
    login_data: LoginRequest,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """Authenticate user and return tokens"""
    # Check login attempts
    allowed, lockout_time = await security_manager.check_login_attempts(login_data.username)
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Too many failed attempts. Try again in {lockout_time} seconds"
        )
    
    # Find user
    result = await db.execute(
        select(User).where(User.username == login_data.username)
    )
    user = result.scalar_one_or_none()
    
    if not user or not security_manager.verify_password(login_data.password, user.hashed_password):
        await security_manager.record_login_attempt(login_data.username, False)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password"
        )
    
    # Check if account is locked
    if user.locked_until and user.locked_until > datetime.utcnow():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Account locked until {user.locked_until}"
        )
    
    # Check if email is verified
    if not user.is_verified:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Email not verified. Please check your inbox."
        )
    
    # Check 2FA if enabled
    if user.two_factor_enabled:
        if not login_data.two_factor_code:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="2FA code required"
            )
        
        # Verify 2FA code
        if not verify_totp(login_data.two_factor_code, user.two_factor_secret):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid 2FA code"
            )
    
    # Record successful login
    await security_manager.record_login_attempt(login_data.username, True)
    
    # Create tokens
    tokens = await security_manager.create_tokens(user.id, user.username, user.role)
    
    # Create session record
    session = Session(
        user_id=user.id,
        session_token=tokens["refresh_token"],
        ip_address=request.client.host,
        user_agent=request.headers.get("user-agent"),
        expires_at=datetime.utcnowfromtimestamp(tokens["refresh_expires_in"]),
        last_activity=datetime.utcnow()
    )
    db.add(session)
    
    # Update last login
    user.last_login = datetime.utcnow()
    await db.commit()
    
    # Return response
    return {
        **tokens,
        "user": user
    }


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(
    refresh_data: RefreshTokenRequest,
    db: AsyncSession = Depends(get_db)
):
    """Refresh access token using refresh token"""
    # Verify refresh token
    payload = await security_manager.verify_token(refresh_data.refresh_token, "refresh")
    
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token"
        )
    
    # Get user
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive"
        )
    
    # Create new tokens
    tokens = await security_manager.create_tokens(user.id, user.username, user.role)
    
    return {
        **tokens,
        "user": user
    }


@router.post("/logout")
async def logout(
    logout_data: LogoutRequest,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db)
):
    """Logout user by revoking tokens"""
    # Revoke access token
    await security_manager.revoke_token(logout_data.access_token)
    
    # Revoke refresh token if provided
    if logout_data.refresh_token:
        await security_manager.revoke_token(logout_data.refresh_token)
        
        # Deactivate session
        result = await db.execute(
            select(Session).where(Session.session_token == logout_data.refresh_token)
        )
        session = result.scalar_one_or_none()
        if session:
            session.is_active = False
            await db.commit()
    
    return {"message": "Successfully logged out"}


@router.post("/forgot-password")
async def forgot_password(
    request: ForgotPasswordRequest,
    db: AsyncSession = Depends(get_db)
):
    """Request password reset"""
    result = await db.execute(select(User).where(User.email == request.email))
    user = result.scalar_one_or_none()
    
    if user:
        # Generate reset token
        token = await security_manager.generate_password_reset_token(user.id)
        
        # Send reset email
        await email_service.send_password_reset_email(user.email, token)
    
    # Always return success to prevent email enumeration
    return {"message": "If your email is registered, you will receive a password reset link"}


@router.post("/reset-password")
async def reset_password(
    reset_data: ResetPasswordRequest,
    db: AsyncSession = Depends(get_db)
):
    """Reset password using token"""
    user_id = await security_manager.verify_password_reset_token(reset_data.token)
    
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired reset token"
        )
    
    # Get user
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Update password
    user.hashed_password = security_manager.get_password_hash(reset_data.new_password)
    user.password_changed_at = datetime.utcnow()
    
    # Invalidate all sessions
    await db.execute(
        select(Session).where(Session.user_id == user.id)
    )
    sessions = result.scalars().all()
    for session in sessions:
        session.is_active = False
        await security_manager.revoke_token(session.session_token)
    
    await db.commit()
    
    return {"message": "Password successfully reset"}


@router.post("/verify-email")
async def verify_email(
    verify_data: VerifyEmailRequest,
    db: AsyncSession = Depends(get_db)
):
    """Verify email address"""
    user_id = await security_manager.verify_email_token(verify_data.token)
    
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired verification token"
        )
    
    # Get user
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    user.is_verified = True
    await db.commit()
    
    return {"message": "Email successfully verified"}


@router.post("/resend-verification")
async def resend_verification(
    request: ResendVerificationRequest,
    db: AsyncSession = Depends(get_db)
):
    """Resend email verification"""
    result = await db.execute(select(User).where(User.email == request.email))
    user = result.scalar_one_or_none()
    
    if user and not user.is_verified:
        token = await security_manager.generate_email_verification_token(user.id)
        await email_service.send_verification_email(user.email, token)
    
    return {"message": "If your email is unverified, a new verification link has been sent"}