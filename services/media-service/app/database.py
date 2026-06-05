# services/media-service/app/database.py
"""Database models and connection for Media Service"""

from datetime import datetime
from typing import Optional, Dict, Any
from uuid import UUID, uuid4
from sqlalchemy import (
    Column, String, DateTime, Integer, Boolean, 
    JSON, ForeignKey, Table, Index, Text
)
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.ext.asyncio import (
    AsyncSession, create_async_engine, async_sessionmaker,
    AsyncAttrs
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, DeclarativeBase
import logging

from .config import settings

logger = logging.getLogger(__name__)

# Database engine
engine = create_async_engine(
    settings.DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://"),
    pool_size=settings.DATABASE_POOL_SIZE,
    max_overflow=settings.DATABASE_MAX_OVERFLOW,
    echo=settings.DEBUG,
    pool_pre_ping=True
)

# Session factory
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False
)


class Base(DeclarativeBase):
    """Base model class"""
    pass


class MediaFile(Base):
    """Media file metadata"""
    __tablename__ = "media_files"
    
    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id = Column(PGUUID(as_uuid=True), nullable=False, index=True)
    filename = Column(String(255), nullable=False)
    original_filename = Column(String(255), nullable=False)
    file_size = Column(Integer, nullable=False)  # bytes
    mime_type = Column(String(100), nullable=False)
    
    # Storage paths
    storage_path = Column(String(500), nullable=False)
    thumbnail_paths = Column(JSON, default=dict)  # size -> path
    public_url = Column(String(500))
    
    # Image metadata
    width = Column(Integer)
    height = Column(Integer)
    blurhash = Column(String(100))  # For progressive loading
    dominant_color = Column(String(7))  # Hex color
    exif_data = Column(JSON, default=dict)
    
    # Processing status
    is_processed = Column(Boolean, default=False)
    processing_error = Column(Text, nullable=True)
    processed_at = Column(DateTime, nullable=True)
    
    # Additional info
    tags = Column(JSON, default=list)
    metadata = Column(JSON, default=dict)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Soft delete
    is_deleted = Column(Boolean, default=False)
    deleted_at = Column(DateTime, nullable=True)
    
    __table_args__ = (
        Index("idx_media_user_created", "user_id", "created_at"),
        Index("idx_media_mime_type", "mime_type"),
        Index("idx_media_is_processed", "is_processed"),
        Index("idx_media_tags", "tags", postgresql_using="gin"),
    )


class UploadSession(Base):
    """Track upload sessions for resumable uploads"""
    __tablename__ = "upload_sessions"
    
    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id = Column(PGUUID(as_uuid=True), nullable=False, index=True)
    upload_id = Column(String(100), unique=True, nullable=False)
    filename = Column(String(255), nullable=False)
    total_size = Column(Integer, nullable=False)
    uploaded_size = Column(Integer, default=0)
    chunk_count = Column(Integer, default=0)
    completed_chunks = Column(JSON, default=list)
    status = Column(String(20), default="in_progress")  # in_progress, completed, failed, expired
    expires_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    __table_args__ = (
        Index("idx_upload_user_status", "user_id", "status"),
        Index("idx_upload_expires", "expires_at"),
    )


class ImageAnalysis(Base):
    """Store image analysis results"""
    __tablename__ = "image_analysis"
    
    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    media_id = Column(PGUUID(as_uuid=True), ForeignKey("media_files.id", ondelete="CASCADE"), nullable=False)
    
    # Quality metrics
    brightness = Column(Integer)  # 0-100
    contrast = Column(Integer)  # 0-100
    sharpness = Column(Integer)  # 0-100
    noise_level = Column(Integer)  # 0-100
    
    # Content detection
    has_plant = Column(Boolean, default=False)
    plant_confidence = Column(Integer)  # 0-100
    disease_regions = Column(JSON, default=list)  # List of bounding boxes
    
    # Color analysis
    dominant_colors = Column(JSON, default=list)  # List of hex colors with percentages
    color_palette = Column(JSON, default=list)
    
    # Quality flags
    is_blurry = Column(Boolean, default=False)
    is_under_exposed = Column(Boolean, default=False)
    is_over_exposed = Column(Boolean, default=False)
    quality_score = Column(Integer, default=0)  # 0-100
    
    analyzed_at = Column(DateTime, default=datetime.utcnow)
    
    __table_args__ = (
        Index("idx_analysis_media", "media_id"),
        Index("idx_analysis_quality", "quality_score"),
    )


async def init_db():
    """Initialize database"""
    async with engine.begin() as conn:
        # Create tables
        await conn.run_sync(Base.metadata.create_all)
        logger.info("Database tables created")
    
    @classmethod
    async def health_check(cls) -> bool:
        """Check database connectivity"""
        try:
            async with AsyncSessionLocal() as session:
                await session.execute("SELECT 1")
            return True
        except Exception as e:
            logger.error(f"Database health check failed: {e}")
            return False


async def get_db() -> AsyncSession:
    """Get database session"""
    async with AsyncSessionLocal() as session:
        yield session