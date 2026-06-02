# services/api-gateway/app/api/v1/sync.py
"""Synchronization API endpoints"""

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from uuid import UUID
from typing import List

from ...schemas.sync import SyncRequest, SyncResponse, SyncStatusResponse
from ...clients.sync_service import SyncServiceClient
from ...core.dependencies import get_current_active_user

router = APIRouter()
sync_client = SyncServiceClient()


@router.post("/upload", response_model=SyncResponse)
async def sync_offline_data(
    sync_request: SyncRequest,
    background_tasks: BackgroundTasks,
    current_user = Depends(get_current_active_user)
):
    """Upload and sync offline data"""
    try:
        # Verify user owns this data
        if sync_request.user_id != current_user["id"]:
            raise HTTPException(
                status_code=403,
                detail="Cannot sync data for another user"
            )
        
        # Process sync in background
        result = await sync_client.sync_offline_data(
            user_id=sync_request.user_id,
            device_id=sync_request.device_id,
            scans=sync_request.scans,
            predictions=sync_request.predictions or []
        )
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Sync failed: {str(e)}"
        )


@router.get("/pending")
async def get_pending_syncs(
    current_user = Depends(get_current_active_user)
):
    """Get pending sync items for user"""
    try:
        pending = await sync_client.get_pending_syncs(current_user["id"])
        return {"pending_items": pending}
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get pending syncs: {str(e)}"
        )


@router.get("/status/{sync_id}", response_model=SyncStatusResponse)
async def get_sync_status(
    sync_id: UUID,
    current_user = Depends(get_current_active_user)
):
    """Get sync status"""
    try:
        status = await sync_client.get_sync_status(str(sync_id))
        return status
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get sync status: {str(e)}"
        )


@router.get("/queue/stats")
async def get_queue_stats(
    device_id: str,
    current_user = Depends(get_current_active_user)
):
    """Get offline queue statistics"""
    try:
        stats = await sync_client.get_offline_queue_stats(device_id)
        return stats
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get queue stats: {str(e)}"
        )