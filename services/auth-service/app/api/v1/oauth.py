# services/auth-service/app/api/v1/oauth.py
"""OAuth authentication endpoints for social login"""

from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from uuid import UUID
import secrets
import httpx
from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_

from ...core.database import get_db
from ...core.security import security_manager
from ...models.user import User, OAuthAccount
from ...schemas.auth import (
    OAuthAuthorizeRequest,
    OAuthAccountResponse,
    TokenResponse
)
from ..dependencies import get_current_user, get_current_active_user
from ...config import settings

router = APIRouter()
security = HTTPBearer()


class OAuthProvider:
    """OAuth provider handler"""
    
    def __init__(self, provider_name: str):
        self.provider_name = provider_name
        
    async def get_auth_url(self, redirect_uri: str, state: str) -> str:
        """Get authorization URL for OAuth provider"""
        if self.provider_name == "google":
            return f"https://accounts.google.com/o/oauth2/v2/auth?client_id={settings.GOOGLE_CLIENT_ID}&redirect_uri={redirect_uri}&response_type=code&scope=email profile&state={state}"
        elif self.provider_name == "github":
            return f"https://github.com/login/oauth/authorize?client_id={settings.GITHUB_CLIENT_ID}&redirect_uri={redirect_uri}&scope=user:email&state={state}"
        else:
            raise ValueError(f"Unsupported provider: {self.provider_name}")
    
    async def exchange_code(self, code: str, redirect_uri: str) -> Dict[str, Any]:
        """Exchange authorization code for access token"""
        async with httpx.AsyncClient() as client:
            if self.provider_name == "google":
                response = await client.post(
                    "https://oauth2.googleapis.com/token",
                    data={
                        "code": code,
                        "client_id": settings.GOOGLE_CLIENT_ID,
                        "client_secret": settings.GOOGLE_CLIENT_SECRET.get_secret_value() if settings.GOOGLE_CLIENT_SECRET else None,
                        "redirect_uri": redirect_uri,
                        "grant_type": "authorization_code"
                    }
                )
                data = response.json()
                
                # Get user info
                user_response = await client.get(
                    "https://www.googleapis.com/oauth2/v2/userinfo",
                    headers={"Authorization": f"Bearer {data['access_token']}"}
                )
                user_info = user_response.json()
                
                return {
                    "provider_user_id": user_info["id"],
                    "email": user_info["email"],
                    "name": user_info.get("name"),
                    "avatar_url": user_info.get("picture"),
                    "access_token": data["access_token"],
                    "refresh_token": data.get("refresh_token"),
                    "expires_in": data["expires_in"]
                }
                
            elif self.provider_name == "github":
                response = await client.post(
                    "https://github.com/login/oauth/access_token",
                    data={
                        "code": code,
                        "client_id": settings.GITHUB_CLIENT_ID,
                        "client_secret": settings.GITHUB_CLIENT_SECRET.get_secret_value() if settings.GITHUB_CLIENT_SECRET else None,
                        "redirect_uri": redirect_uri
                    },
                    headers={"Accept": "application/json"}
                )
                data = response.json()
                
                # Get user info
                user_response = await client.get(
                    "https://api.github.com/user",
                    headers={"Authorization": f"Bearer {data['access_token']}"}
                )
                user_info = user_response.json()
                
                # Get email (may be private)
                email_response = await client.get(
                    "https://api.github.com/user/emails",
                    headers={"Authorization": f"Bearer {data['access_token']}"}
                )
                emails = email_response.json()
                primary_email = next((e for e in emails if e.get("primary")), emails[0]) if emails else {}
                
                return {
                    "provider_user_id": str(user_info["id"]),
                    "email": primary_email.get("email"),
                    "name": user_info.get("name") or user_info.get("login"),
                    "avatar_url": user_info.get("avatar_url"),
                    "access_token": data["access_token"],
                    "expires_in": data.get("expires_in", 3600)
                }
            else:
                raise ValueError(f"Unsupported provider: {self.provider_name}")


@router.get("/{provider}/authorize")
async def oauth_authorize(
    provider: str,
    redirect_uri: str,
    state: Optional[str] = None
):
    """Initiate OAuth authorization flow"""
    if provider not in ["google", "github"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported provider: {provider}"
        )
    
    # Generate state if not provided
    if not state:
        state = secrets.token_urlsafe(32)
    
    # Store state in Redis for validation
    await security_manager.redis_client.setex(
        f"oauth_state:{state}",
        600,  # 10 minutes
        redirect_uri
    )
    
    # Get authorization URL
    oauth = OAuthProvider(provider)
    auth_url = await oauth.get_auth_url(redirect_uri, state)
    
    return {"auth_url": auth_url, "state": state}


@router.post("/{provider}/callback", response_model=TokenResponse)
async def oauth_callback(
    provider: str,
    request: OAuthAuthorizeRequest,
    db: AsyncSession = Depends(get_db)
):
    """Handle OAuth callback and authenticate user"""
    if provider not in ["google", "github"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported provider: {provider}"
        )
    
    # Validate state
    stored_redirect_uri = await security_manager.redis_client.get(f"oauth_state:{request.state}")
    if not stored_redirect_uri:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired state parameter"
        )
    
    await security_manager.redis_client.delete(f"oauth_state:{request.state}")
    
    # Exchange code for user info
    oauth = OAuthProvider(provider)
    try:
        user_info = await oauth.exchange_code(request.code, request.redirect_uri)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to exchange code: {str(e)}"
        )
    
    # Check if OAuth account exists
    result = await db.execute(
        select(OAuthAccount).where(
            and_(
                OAuthAccount.provider == provider,
                OAuthAccount.provider_user_id == user_info["provider_user_id"]
            )
        )
    )
    oauth_account = result.scalar_one_or_none()
    
    if oauth_account:
        # Existing OAuth account - login user
        user = await db.get(User, oauth_account.user_id)
        if not user or not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User account not found or inactive"
            )
        
        # Update OAuth tokens
        oauth_account.access_token = user_info.get("access_token")
        oauth_account.refresh_token = user_info.get("refresh_token")
        if user_info.get("expires_in"):
            oauth_account.expires_at = datetime.utcnow() + timedelta(seconds=user_info["expires_in"])
        oauth_account.updated_at = datetime.utcnow()
        
        await db.commit()
        
    else:
        # New OAuth account - check if email exists
        email = user_info.get("email")
        user = None
        
        if email:
            result = await db.execute(select(User).where(User.email == email))
            user = result.scalar_one_or_none()
        
        if not user:
            # Create new user
            username = f"{provider}_{user_info['provider_user_id']}"
            # Ensure unique username
            result = await db.execute(select(User).where(User.username == username))
            if result.scalar_one_or_none():
                username = f"{username}_{secrets.token_hex(4)}"
            
            user = User(
                email=email or f"{username}@temp.agriculture-ai.com",
                username=username,
                hashed_password=security_manager.get_password_hash(secrets.token_urlsafe(32)),
                full_name=user_info.get("name"),
                profile_picture_url=user_info.get("avatar_url"),
                is_verified=bool(email),  # Auto-verify if email provided
                role="farmer"
            )
            db.add(user)
            await db.flush()
        
        # Create OAuth account record
        oauth_account = OAuthAccount(
            user_id=user.id,
            provider=provider,
            provider_user_id=user_info["provider_user_id"],
            access_token=user_info.get("access_token"),
            refresh_token=user_info.get("refresh_token"),
            expires_at=datetime.utcnow() + timedelta(seconds=user_info.get("expires_in", 3600)) if user_info.get("expires_in") else None
        )
        db.add(oauth_account)
        await db.commit()
        await db.refresh(user)
    
    # Create tokens
    tokens = await security_manager.create_tokens(user.id, user.username, user.role)
    
    # Update last login
    user.last_login = datetime.utcnow()
    await db.commit()
    
    return {
        **tokens,
        "user": user
    }


@router.get("/accounts", response_model=list[OAuthAccountResponse])
async def get_oauth_accounts(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Get user's connected OAuth accounts"""
    result = await db.execute(
        select(OAuthAccount).where(OAuthAccount.user_id == current_user.id)
    )
    accounts = result.scalars().all()
    
    return [
        {
            "provider": acc.provider,
            "provider_user_id": acc.provider_user_id,
            "created_at": acc.created_at
        }
        for acc in accounts
    ]


@router.delete("/{provider}")
async def disconnect_oauth(
    provider: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Disconnect OAuth account"""
    # Check if user has password set
    if not current_user.hashed_password or current_user.hashed_password.startswith("$2b$"):
        # User might only have OAuth login
        oauth_count = await db.execute(
            select(OAuthAccount).where(OAuthAccount.user_id == current_user.id)
        )
        if len(oauth_count.scalars().all()) <= 1:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot disconnect only login method. Please set a password first."
            )
    
    result = await db.execute(
        select(OAuthAccount).where(
            and_(
                OAuthAccount.user_id == current_user.id,
                OAuthAccount.provider == provider
            )
        )
    )
    oauth_account = result.scalar_one_or_none()
    
    if not oauth_account:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="OAuth account not found"
        )
    
    await db.delete(oauth_account)
    await db.commit()
    
    return {"message": f"{provider} account disconnected successfully"}