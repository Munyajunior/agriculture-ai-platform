# services/api-gateway/app/schemas/sync.py
"""Synchronization schemas"""

from typing import Optional, List, Dict, Any
from uuid import UUID
from datetime import datetime
from pydantic import BaseModel, Field


class OfflineData(BaseModel):
    """Offline data structure"""
    scan_id: Optional[str] = None
    image_base64: str
    captured_at: datetime
    location_lat: Optional[float] = None
    location_lon: Optional[float] = None
    edge_prediction: Optional[Dict[str, Any]] = None


class SyncRequest(BaseModel):
    """Sync request schema"""
    device_id: str
    user_id: UUID
    scans: List[OfflineData]
    predictions: Optional[List[Dict[str, Any]]] = None
    telemetry: Optional[List[Dict[str, Any]]] = None


class SyncResponse(BaseModel):
    """Sync response schema"""
    sync_id: UUID
    synced_scans: int
    synced_predictions: int
    failed_items: List[str]
    new_models_available: bool
    latest_model_version: Optional[str] = None
    sync_duration_ms: int


class SyncStatusResponse(BaseModel):
    """Sync status response"""
    sync_id: UUID
    status: str  # pending, processing, completed, failed
    progress: float = Field(..., ge=0, le=100)
    total_items: int
    processed_items: int
    failed_items: int
    started_at: datetime
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None