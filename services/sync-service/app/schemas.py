# services/sync-service/app/schemas.py
"""Pydantic schemas for Sync Service"""

from datetime import datetime
from typing import Optional, List, Dict, Any
from uuid import UUID
from pydantic import BaseModel, Field

from .database import SyncStatus, EntityType


class SyncItem(BaseModel):
    """Sync item schema"""
    entity_type: EntityType
    entity_id: str
    data: Dict[str, Any]
    version: int = 1
    operation: str = "update"  # create, update, delete


class SyncRequest(BaseModel):
    """Sync request schema"""
    device_id: str
    sync_token: Optional[str] = None
    changes: List[Dict[str, Any]] = Field(default_factory=list)
    last_sync_at: Optional[datetime] = None


class SyncResponse(BaseModel):
    """Sync response schema"""
    sync_id: str
    status: str
    message: str
    synced_items: List[str]
    failed_items: List[str]
    pending_items: List[Dict[str, Any]]
    new_sync_token: Optional[str]


class BatchSyncRequest(BaseModel):
    """Batch sync request"""
    requests: List[SyncRequest]


class SyncStatusResponse(BaseModel):
    """Sync status response"""
    device_id: str
    is_registered: bool
    last_sync_at: Optional[str]
    last_heartbeat: Optional[str]
    pending_syncs: int
    total_syncs: int
    successful_syncs: int
    failed_syncs: int
    is_active: bool


class DeviceRegisterRequest(BaseModel):
    """Device registration request"""
    device_id: str
    device_model: Optional[str] = None
    os_version: Optional[str] = None
    app_version: Optional[str] = None
    supports_edge_inference: bool = False
    storage_available_mb: Optional[int] = None
    battery_level: Optional[int] = Field(None, ge=0, le=100)


class DeviceResponse(BaseModel):
    """Device response"""
    id: UUID
    device_id: str
    user_id: UUID
    device_model: Optional[str]
    os_version: Optional[str]
    app_version: Optional[str]
    supports_edge_inference: bool
    is_active: bool
    last_heartbeat: datetime
    created_at: datetime


class ConflictResponse(BaseModel):
    """Conflict response"""
    id: UUID
    entity_type: str
    entity_id: str
    client_version: Dict[str, Any]
    server_version: Dict[str, Any]
    resolution_strategy: str
    status: str
    created_at: datetime


class ConflictResolutionRequest(BaseModel):
    """Conflict resolution request"""
    resolution: Dict[str, Any]  # Resolved data
    strategy: str = "manual"  # manual, last_write_wins, server_wins, client_wins, merge