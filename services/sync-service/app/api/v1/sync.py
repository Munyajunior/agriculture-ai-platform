# services/sync-service/app/api/v1/sync.py
"""Sync API endpoints"""

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, status
from typing import List, Optional, Dict, Any
from uuid import UUID

from ...core.sync_engine import SyncEngine
from ...core.queue_manager import QueueManager
from ...database import SyncStatus
from ...schemas import (
    SyncRequest, SyncResponse, SyncStatusResponse,
    BatchSyncRequest, SyncItem
)
from .dependencies import verify_device

router = APIRouter()
sync_engine = SyncEngine()
queue_manager = QueueManager()


@router.post("/", response_model=SyncResponse)
async def sync_device(
    request: SyncRequest,
    background_tasks: BackgroundTasks,
    device_info: Dict[str, Any] = Depends(verify_device)
):
    """
    Synchronize device data with cloud
    Supports incremental sync with sync_token
    """
    
    try:
        # Process sync in background for large payloads
        if len(request.changes) > 100:
            background_tasks.add_task(
                sync_engine.sync_device,
                device_info['device_id'],
                device_info['user_id'],
                request.sync_token,
                request.changes
            )
            
            return SyncResponse(
                sync_id="async",
                status="accepted",
                message="Sync processing in background",
                synced_items=[],
                failed_items=[],
                pending_items=[],
                new_sync_token=None
            )
        
        # Process sync immediately
        result = await sync_engine.sync_device(
            device_info['device_id'],
            device_info['user_id'],
            request.sync_token,
            request.changes
        )
        
        return SyncResponse(
            sync_id=result['sync_id'],
            status="success",
            message="Sync completed successfully",
            synced_items=result['synced_items'],
            failed_items=result['failed_items'],
            pending_items=result['pending_items'],
            new_sync_token=result['new_sync_token']
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Sync failed: {str(e)}"
        )


@router.post("/batch", response_model=List[SyncResponse])
async def batch_sync(
    requests: List[SyncRequest],
    device_info: Dict[str, Any] = Depends(verify_device)
):
    """Batch sync multiple entities"""
    
    results = []
    
    for request in requests:
        try:
            result = await sync_engine.sync_device(
                device_info['device_id'],
                device_info['user_id'],
                request.sync_token,
                request.changes
            )
            results.append(SyncResponse(
                sync_id=result['sync_id'],
                status="success",
                message="Sync completed",
                synced_items=result['synced_items'],
                failed_items=result['failed_items'],
                pending_items=result['pending_items'],
                new_sync_token=result['new_sync_token']
            ))
        except Exception as e:
            results.append(SyncResponse(
                sync_id="error",
                status="failed",
                message=str(e),
                synced_items=[],
                failed_items=[],
                pending_items=[],
                new_sync_token=None
            ))
    
    return results


@router.get("/status/{device_id}", response_model=SyncStatusResponse)
async def get_sync_status(device_id: str):
    """Get sync status for a device"""
    
    status = await sync_engine.get_sync_status(device_id)
    return SyncStatusResponse(**status)


@router.post("/queue/add")
async def add_to_sync_queue(
    items: List[SyncItem],
    device_info: Dict[str, Any] = Depends(verify_device)
):
    """Add items to sync queue for later processing"""
    
    queued_items = []
    
    for item in items:
        item_id = await sync_engine.enqueue_sync_item(
            device_id=device_info['device_id'],
            user_id=device_info['user_id'],
            entity_type=item.entity_type,
            entity_id=item.entity_id,
            entity_data=item.data.dict(),
            version=item.version
        )
        queued_items.append(item_id)
    
    return {
        "message": f"Added {len(queued_items)} items to sync queue",
        "queued_ids": queued_items
    }


@router.post("/queue/process")
async def process_sync_queue(
    limit: int = 100,
    device_info: Dict[str, Any] = Depends(verify_device)
):
    """Process items in sync queue"""
    
    result = await sync_engine.sync_device(
        device_info['device_id'],
        device_info['user_id'],
        None,
        None
    )
    
    return result


@router.delete("/queue/{item_id}")
async def remove_from_queue(
    item_id: UUID,
    device_info: Dict[str, Any] = Depends(verify_device)
):
    """Remove item from sync queue"""
    
    await queue_manager.remove_item(item_id)
    
    return {"message": f"Item {item_id} removed from queue"}
