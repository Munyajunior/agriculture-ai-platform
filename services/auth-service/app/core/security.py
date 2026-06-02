# services/auth-service/app/core/security.py
"""Security utilities for authentication"""

from datetime import datetime, timedelta
from typing import Optional, Dict, Any, Tuple
from uuid import UUID, uuid4
import hashlib
import hmac
import secrets
from passlib.context import CryptContext
from jose import JWTError, jwt
from fastapi import HTTPException, status

from ..config import settings
from .redis_client import redis_client

# Password hashing context
pwd_context = CryptContext(
    schemes=["argon2"],
    deprecated="auto",
    argon2__rounds=12
)


class SecurityManager:
    """Manages authentication and security operations"""
    
    def __init__(self):
        self._initialized = False
        self._blacklist_prefix = "blacklist:"
        self._login_attempts_prefix = "login_attempts:"
        self._lockout_prefix = "lockout:"
        
    async def initialize(self):
        """Initialize security manager"""
        self._initialized = True
        
    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        """Verify password against hash"""
        return pwd_context.verify(plain_password, hashed_password)
    
    def get_password_hash(self, password: str) -> str:
        """Hash password using argon2"""
        return pwd_context.hash(password)
    
    async def create_tokens(self, user_id: UUID, username: str, role: str) -> Dict[str, Any]:
        """Create access and refresh tokens"""
        # Access token (short-lived)
        access_token_data = {
            "sub": str(user_id),
            "username": username,
            "role": role,
            "type": "access",
            "jti": str(uuid4()),
            "iat": datetime.utcnow(),
            "exp": datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
            "iss": settings.JWT_ISSUER,
            "aud": settings.JWT_AUDIENCE
        }
        
        access_token = jwt.encode(
            access_token_data,
            settings.SECRET_KEY,
            algorithm=settings.ALGORITHM
        )
        
        # Refresh token (longer-lived)
        refresh_token_data = {
            "sub": str(user_id),
            "username": username,
            "type": "refresh",
            "jti": str(uuid4()),
            "iat": datetime.utcnow(),
            "exp": datetime.utcnow() + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
            "iss": settings.JWT_ISSUER,
            "aud": settings.JWT_AUDIENCE
        }
        
        refresh_token = jwt.encode(
            refresh_token_data,
            settings.SECRET_KEY,
            algorithm=settings.ALGORITHM
        )
        
        # Store refresh token in Redis for validation
        await redis_client.setex(
            f"refresh_token:{refresh_token_data['jti']}",
            settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 3600,
            str(user_id)
        )
        
        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
            "expires_in": settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            "refresh_expires_in": settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 3600
        }
    
    async def verify_token(self, token: str, token_type: str = "access") -> Dict[str, Any]:
        """Verify JWT token and return payload"""
        try:
            payload = jwt.decode(
                token,
                settings.SECRET_KEY,
                algorithms=[settings.ALGORITHM],
                audience=settings.JWT_AUDIENCE,
                issuer=settings.JWT_ISSUER
            )
            
            # Check token type
            if payload.get("type") != token_type:
                raise JWTError("Invalid token type")
            
            # Check if token is blacklisted
            is_blacklisted = await redis_client.exists(
                f"{self._blacklist_prefix}{payload.get('jti')}"
            )
            if is_blacklisted:
                raise JWTError("Token has been revoked")
            
            # For refresh tokens, verify in Redis
            if token_type == "refresh":
                stored = await redis_client.get(f"refresh_token:{payload.get('jti')}")
                if not stored:
                    raise JWTError("Refresh token not found")
            
            return payload
            
        except JWTError as e:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Invalid token: {str(e)}",
                headers={"WWW-Authenticate": "Bearer"}
            )
    
    async def revoke_token(self, token: str) -> bool:
        """Revoke a token (add to blacklist)"""
        try:
            payload = jwt.decode(
                token,
                settings.SECRET_KEY,
                algorithms=[settings.ALGORITHM],
                options={"verify_exp": False}
            )
            
            jti = payload.get("jti")
            exp = payload.get("exp")
            
            if jti and exp:
                # Calculate remaining TTL
                ttl = max(exp - datetime.utcnow().timestamp(), 0)
                if ttl > 0:
                    await redis_client.setex(
                        f"{self._blacklist_prefix}{jti}",
                        int(ttl),
                        "revoked"
                    )
                
                # Remove refresh token if exists
                await redis_client.delete(f"refresh_token:{jti}")
                
                return True
        except:
            pass
        
        return False
    
    async def check_login_attempts(self, username: str) -> Tuple[bool, int]:
        """Check if user is locked out and get attempt count"""
        lockout_key = f"{self._lockout_prefix}{username}"
        attempts_key = f"{self._login_attempts_prefix}{username}"
        
        # Check if locked out
        lockout_ttl = await redis_client.ttl(lockout_key)
        if lockout_ttl > 0:
            return False, lockout_ttl
        
        # Get attempt count
        attempts = await redis_client.get(attempts_key) or 0
        attempts = int(attempts)
        
        return True, attempts
    
    async def record_login_attempt(self, username: str, success: bool):
        """Record login attempt for rate limiting"""
        attempts_key = f"{self._login_attempts_prefix}{username}"
        
        if not success:
            # Increment failed attempts
            attempts = await redis_client.incr(attempts_key)
            await redis_client.expire(attempts_key, 3600)  # Reset after 1 hour
            
            # Lockout if max attempts reached
            if attempts >= settings.MAX_LOGIN_ATTEMPTS:
                lockout_key = f"{self._lockout_prefix}{username}"
                await redis_client.setex(
                    lockout_key,
                    settings.LOCKOUT_DURATION_MINUTES * 60,
                    "locked"
                )
        else:
            # Clear attempts on successful login
            await redis_client.delete(attempts_key)
    
    async def generate_password_reset_token(self, user_id: UUID) -> str:
        """Generate password reset token"""
        token = secrets.token_urlsafe(32)
        key = f"password_reset:{token}"
        await redis_client.setex(
            key,
            settings.PASSWORD_RESET_TOKEN_EXPIRE_HOURS * 3600,
            str(user_id)
        )
        return token
    
    async def verify_password_reset_token(self, token: str) -> Optional[UUID]:
        """Verify password reset token and return user ID"""
        key = f"password_reset:{token}"
        user_id_str = await redis_client.get(key)
        
        if user_id_str:
            await redis_client.delete(key)
            return UUID(user_id_str)
        
        return None
    
    async def generate_email_verification_token(self, user_id: UUID) -> str:
        """Generate email verification token"""
        token = secrets.token_urlsafe(32)
        key = f"email_verification:{token}"
        await redis_client.setex(key, 86400 * 7, str(user_id))  # 7 days
        return token
    
    async def verify_email_token(self, token: str) -> Optional[UUID]:
        """Verify email verification token"""
        key = f"email_verification:{token}"
        user_id_str = await redis_client.get(key)
        
        if user_id_str:
            await redis_client.delete(key)
            return UUID(user_id_str)
        
        return None
    
    def hash_api_key(self, api_key: str) -> str:
        """Hash API key for storage"""
        return hashlib.sha256(api_key.encode()).hexdigest()
    
    def generate_api_key(self) -> Tuple[str, str]:
        """Generate new API key pair (key, hashed)"""
        api_key = f"agri_{secrets.token_urlsafe(32)}"
        hashed = self.hash_api_key(api_key)
        return api_key, hashed
    
    def verify_api_key(self, api_key: str, hashed: str) -> bool:
        """Verify API key against hash"""
        return hmac.compare_digest(self.hash_api_key(api_key), hashed)


# Global security manager instance
security_manager = SecurityManager()