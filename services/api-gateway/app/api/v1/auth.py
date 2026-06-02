# services/api-gateway/app/api/v1/auth.py
"""Authentication API endpoints"""

from fastapi import APIRouter, Depends, HTTPException, status, Response, Request
from slowapi import Limiter
from slowapi.util import get_remote_address

from ...schemas.auth import (
    UserRegister,
    UserLogin,
    TokenResponse,
    UserResponse,
    RefreshTokenRequest,
    ChangePasswordRequest,
    ForgotPasswordRequest,
    ResetPasswordRequest
)
from ...clients.auth_service import AuthServiceClient
from ...core.rate_limiter import auth_limiter
from ...core.redis_client import redis_client

router = APIRouter()
auth_client = AuthServiceClient()


@router.post("/register", response_model=UserResponse)
async def register_user(
    user_data: UserRegister,
    request: Request,
    rate_limiter=Depends(auth_limiter)
):
    """Register new user account"""
    try:
        # Check if user exists
        existing_user = await auth_client.get_user_by_email(user_data.email)
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered"
            )
        
        # Create user
        user = await auth_client.register_user(user_data.dict())
        
        # Track registration event
        # await analytics_client.track_event("user_registered", user["id"])
        
        return user
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Registration failed: {str(e)}"
        )


@router.post("/login", response_model=TokenResponse)
async def login_user(
    login_data: UserLogin,
    response: Response,
    request: Request,
    rate_limiter=Depends(auth_limiter)
):
    """Login user and return tokens"""
    try:
        # Authenticate user
        tokens = await auth_client.login(login_data.dict())
        
        # Set refresh token as HTTP-only cookie
        response.set_cookie(
            key="refresh_token",
            value=tokens["refresh_token"],
            httponly=True,
            secure=True,
            samesite="strict",
            max_age=7 * 24 * 60 * 60  # 7 days
        )
        
        # Store token in Redis for validation
        await redis_client.set(
            f"user_session:{tokens['user']['id']}",
            tokens["access_token"],
            expire=tokens["expires_in"]
        )
        
        return tokens
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials"
        )


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(
    request: Request,
    refresh_token_data: Optional[RefreshTokenRequest] = None
):
    """Refresh access token"""
    try:
        # Get refresh token from request body or cookie
        refresh_token = None
        if refresh_token_data:
            refresh_token = refresh_token_data.refresh_token
        else:
            refresh_token = request.cookies.get("refresh_token")
        
        if not refresh_token:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Refresh token required"
            )
        
        # Refresh tokens
        tokens = await auth_client.refresh_token(refresh_token)
        
        return tokens
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token"
        )


@router.post("/logout")
async def logout_user(request: Request):
    """Logout user and invalidate tokens"""
    try:
        # Get token from Authorization header
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header.split(" ")[1]
            
            # Blacklist token
            await redis_client.set(f"blacklist:{token}", "true", expire=24 * 60 * 60)
        
        # Clear cookie
        response = Response()
        response.delete_cookie("refresh_token")
        
        return {"message": "Successfully logged out"}
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Logout failed: {str(e)}"
        )


@router.post("/change-password")
async def change_password(
    password_data: ChangePasswordRequest,
    current_user = Depends(get_current_active_user)
):
    """Change user password"""
    try:
        await auth_client.change_password(
            current_user["id"],
            password_data.dict()
        )
        
        return {"message": "Password changed successfully"}
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to change password"
        )


@router.post("/forgot-password")
async def forgot_password(
    request: ForgotPasswordRequest,
    rate_limiter=Depends(auth_limiter)
):
    """Request password reset"""
    try:
        await auth_client.forgot_password(request.email)
        
        # Always return success even if email doesn't exist (security)
        return {"message": "If email exists, reset instructions will be sent"}
        
    except Exception:
        # Still return success for security
        return {"message": "If email exists, reset instructions will be sent"}


@router.post("/reset-password")
async def reset_password(
    reset_data: ResetPasswordRequest,
    rate_limiter=Depends(auth_limiter)
):
    """Reset password with token"""
    try:
        await auth_client.reset_password(
            reset_data.token,
            reset_data.new_password
        )
        
        return {"message": "Password reset successfully"}
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired reset token"
        )


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(
    current_user = Depends(get_current_active_user)
):
    """Get current user information"""
    return current_user


@router.put("/me")
async def update_current_user(
    user_update: dict,
    current_user = Depends(get_current_active_user)
):
    """Update current user information"""
    try:
        updated_user = await auth_client.update_user(
            current_user["id"],
            user_update
        )
        
        return updated_user
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Update failed: {str(e)}"
        )