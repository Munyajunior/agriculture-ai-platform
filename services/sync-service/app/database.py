# services/sync-service/app/database.py
"""Database models for Sync Service"""

from datetime import datetime
from typing import Optional, Dict, Any
from uuid import UUID, uuid4
from sqlalchemy import (
    Column, String, DateTime, Integer, Boolean, 
    JSON, ForeignKey, Text, Enum, Index, Float
)
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.ext.asyncio import (
    AsyncSession, create_async_engine, async_sessionmaker
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
import enum
import logging

from .config import settings

logger = logging.getLogger(__name__)

engine = create_async_engine(
    settings.DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://"),
    pool_size=20,
    max_overflow=40,
    echo=settings.DEBUG
)

AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)
Base = declarative_base()


class SyncStatus(str, enum.Enum):
    """Sync status enum"""
    PENDING = "pending"
    SYNCING = "syncing"
    COMPLETED = "completed"
    FAILED = "failed"
    CONFLICT = "conflict"


class EntityType(str, enum.Enum):
    """Entity types for sync"""
    SCAN = "scan"
    PREDICTION = "prediction"
    USER = "user"
    FARM = "farm"
    DEVICE = "device"
    TELEMETRY = "telemetry"


class ConflictStrategy(str, enum.Enum):
    """Conflict resolution strategies"""
    LAST_WRITE_WINS = "last_write_wins"
    SERVER_WINS = "server_wins"
    CLIENT_WINS = "client_wins"
    MERGE = "merge"
    MANUAL = "manual"


class SyncQueue(Base):
    """Sync queue for pending items"""
    __tablename__ = "sync_queue"
    
    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    device_id = Column(String(200), nullable=False, index=True)
    user_id = Column(PGUUID(as_uuid=True), nullable=False, index=True)
    
    entity_type = Column(Enum(EntityType), nullable=False)
    entity_id = Column(String(200), nullable=False)
    entity_data = Column(JSON, nullable=False)
    
    # Sync metadata
    sync_status = Column(Enum(SyncStatus), default=SyncStatus.PENDING)
    retry_count = Column(Integer, default=0)
    max_retries = Column(Integer, default=5)
    
    # Version tracking
    version = Column(Integer, default=1)
    last_modified = Column(DateTime, nullable=False)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    synced_at = Column(DateTime, nullable=True)
    
    # Error tracking
    error_message = Column(Text, nullable=True)
    
    __table_args__ = (
        Index("idx_sync_queue_status", "sync_status", "created_at"),
        Index("idx_sync_queue_device_status", "device_id", "sync_status"),
        Index("idx_sync_queue_entity", "entity_type", "entity_id"),
    )


class SyncLog(Base):
    """Sync operation log"""
    __tablename__ = "sync_logs"
    
    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    sync_id = Column(String(100), nullable=False, index=True)
    device_id = Column(String(200), nullable=False, index=True)
    user_id = Column(PGUUID(as_uuid=True), nullable=False)
    
    # Sync details
    entities_synced = Column(Integer, default=0)
    entities_failed = Column(Integer, default=0)
    total_size_bytes = Column(Integer, default=0)
    duration_ms = Column(Integer)
    
    # Status
    status = Column(Enum(SyncStatus), nullable=False)
    error_message = Column(Text, nullable=True)
    
    # Timestamps
    started_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
    
    __table_args__ = (
        Index("idx_sync_logs_device", "device_id", "started_at"),
        Index("idx_sync_logs_sync", "sync_id"),
        Index("idx_sync_logs_status", "status"),
    )


class SyncConflict(Base):
    """Sync conflict records"""
    __tablename__ = "sync_conflicts"
    
    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    entity_type = Column(Enum(EntityType), nullable=False)
    entity_id = Column(String(200), nullable=False)
    
    # Conflicting versions
    client_version = Column(JSON, nullable=False)
    server_version = Column(JSON, nullable=False)
    
    # Resolution
    resolution_strategy = Column(Enum(ConflictStrategy), nullable=False)
    resolved_version = Column(JSON, nullable=True)
    resolved_by = Column(String(100), nullable=True)
    resolved_at = Column(DateTime, nullable=True)
    
    # Status
    status = Column(String(50), default="pending")  # pending, resolved, ignored
    
    created_at = Column(DateTime, default=datetime.utcnow)
    
    __table_args__ = (
        Index("idx_conflicts_entity", "entity_type", "entity_id"),
        Index("idx_conflicts_status", "status"),
    )


class DeviceSyncState(Base):
    """Track sync state per device"""
    __tablename__ = "device_sync_state"
    
    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    device_id = Column(String(200), unique=True, nullable=False, index=True)
    user_id = Column(PGUUID(as_uuid=True), nullable=False)
    
    # Sync state
    last_sync_token = Column(String(500), nullable=True)
    last_sync_at = Column(DateTime, nullable=True)
    last_heartbeat = Column(DateTime, default=datetime.utcnow)
    
    # Device info
    device_model = Column(String(100))
    os_version = Column(String(50))
    app_version = Column(String(50))
    
    # Capabilities
    supports_edge_inference = Column(Boolean, default=False)
    storage_available_mb = Column(Integer)
    battery_level = Column(Integer)
    
    # Sync statistics
    total_syncs = Column(Integer, default=0)
    successful_syncs = Column(Integer, default=0)
    failed_syncs = Column(Integer, default=0)
    
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    __table_args__ = (
        Index("idx_device_user", "user_id", "device_id"),
        Index("idx_device_active", "is_active", "last_heartbeat"),
    )


async def init_db():
    """Initialize database"""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        logger.info("Database tables created")


async def get_db() -> AsyncSession:
    """Get database session"""
    async with AsyncSessionLocal() as session:
        yield session
