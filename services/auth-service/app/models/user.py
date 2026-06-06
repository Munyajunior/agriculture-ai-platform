# services/auth-service/app/models/user.py
from agriculture_ai.types.models import Base, User
from datetime import datetime, timezone
from typing import Optional, List
from uuid import UUID, uuid4
from sqlalchemy import Column, String, DateTime, Boolean, Integer, JSON, Table, Index, ForeignKey
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import relationship

class APIKey(Base):
    """API key model for programmatic access"""
    __tablename__ = "api_keys"
    
    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id = Column(PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(100), nullable=False)
    key_hash = Column(String(255), unique=True, nullable=False)
    last_used_at = Column(DateTime, nullable=True)
    expires_at = Column(DateTime, nullable=True)
    is_active = Column(Boolean, default=True)
    permissions = Column(JSON, default=list)  # List of permissions/scopes
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    
    # Relationships
    user = relationship("User", back_populates="api_keys")


class OAuthAccount(Base):
    """OAuth account associations"""
    __tablename__ = "oauth_accounts"
    
    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id = Column(PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    provider = Column(String(50), nullable=False)  # google, github, etc.
    provider_user_id = Column(String(255), nullable=False)
    access_token = Column(String(500), nullable=True)
    refresh_token = Column(String(500), nullable=True)
    expires_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    
    # Relationships
    user = relationship("User", back_populates="oauth_accounts")
    
    __table_args__ = (
        Index("idx_oauth_provider_id", "provider", "provider_user_id", unique=True),
    )


class PasswordReset(Base):
    """Password reset tokens"""
    __tablename__ = "password_resets"
    
    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id = Column(PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    token = Column(String(255), unique=True, nullable=False, index=True)
    used = Column(Boolean, default=False)
    expires_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class Session(Base):
    """User session tracking"""
    __tablename__ = "sessions"
    
    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id = Column(PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    session_token = Column(String(255), unique=True, nullable=False, index=True)
    ip_address = Column(String(45))
    user_agent = Column(String(500))
    device_info = Column(JSON, default={})
    is_active = Column(Boolean, default=True)
    expires_at = Column(DateTime, nullable=False)
    last_activity = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    
    __table_args__ = (
        Index("idx_session_user", "user_id", "is_active"),
        Index("idx_session_expires", "expires_at"),
    )
