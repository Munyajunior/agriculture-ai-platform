# services/sync-service/app/api/v1/devices.py
"""Device management endpoints"""

from fastapi import APIRouter, Depends, HTTPException, status
from typing import List, Optional
from datetime import datetime
from uuid import UUID

from ...database import AsyncSessionLocal, DeviceSyncState
from ...core.sync_engine import SyncEngine
from ...schemas import DeviceRegisterRequest, DeviceResponse
from ..dependencies import verify_device

router = APIRouter()
sync_engine = SyncEngine()


@router.post("/register", response_model=DeviceResponse)
async def register_device(
    request: DeviceRegisterRequest,
    user_id: UUID = Depends(verify_device)
):
    """Register a new device for sync"""
    
    async with AsyncSessionLocal() as session:
        # Check if device already exists
        from sqlalchemy import select
        
        result = await session.execute(
            select(DeviceSyncState).where(DeviceSyncState.device_id == request.device_id)
        )
        existing = result.scalar_one_or_none()
        
        if existing:
            # Update existing device
            existing.device_model = request.device_model
            existing.os_version = request.os_version
            existing.app_version = request.app_version
            existing.supports_edge_inference = request.supports_edge_inference
            existing.storage_available_mb = request.storage_available_mb
            existing.battery_level = request.battery_level
            existing.last_heartbeat = datetime.utcnow()
            existing.is_active = True
            
            await session.commit()
            await session.refresh(existing)
            
            return DeviceResponse(
                id=existing.id,
                device_id=existing.device_id,
                user_id=existing.user_id,
                device_model=existing.device_model,
                os_version=existing.os_version,
                app_version=existing.app_version,
                supports_edge_inference=existing.supports_edge_inference,
                is_active=existing.is_active,
                last_heartbeat=existing.last_heartbeat,
                created_at=existing.created_at
            )
        else:
            # Create new device
            device = DeviceSyncState(
                device_id=request.device_id,
                user_id=user_id,
                device_model=request.device_model,
                os_version=request.os_version,
                app_version=request.app_version,
                supports_edge_inference=request.supports_edge_inference,
                storage_available_mb=request.storage_available_mb,
                battery_level=request.battery_level,
                last_heartbeat=datetime.utcnow(),
                is_active=True
            )
            
            session.add(device)
            await session.commit()
            await session.refresh(device)
            
            return DeviceResponse(
                id=device.id,
                device_id=device.device_id,
                user_id=device.user_id,
                device_model=device.device_model,
                os_version=device.os_version,
                app_version=device.app_version,
                supports_edge_inference=device.supports_edge_inference,
                is_active=device.is_active,
                last_heartbeat=device.last_heartbeat,
                created_at=device.created_at
            )


@router.post("/heartbeat")
async def device_heartbeat(
    device_id: str,
    battery_level: Optional[int] = None,
    storage_available_mb: Optional[int] = None,
    user_id: UUID = Depends(verify_device)
):
    """Update device heartbeat"""
    
    from sqlalchemy import select, update
    
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(DeviceSyncState).where(DeviceSyncState.device_id == device_id)
        )
        device = result.scalar_one_or_none()
        
        if not device:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Device not registered"
            )
        
        # Update heartbeat
        await session.execute(
            update(DeviceSyncState)
            .where(DeviceSyncState.device_id == device_id)
            .values(
                last_heartbeat=datetime.utcnow(),
                battery_level=battery_level if battery_level is not None else device.battery_level,
                storage_available_mb=storage_available_mb if storage_available_mb is not None else device.storage_available_mb
            )
        )
        
        await session.commit()
        
        return {
            "device_id": device_id,
            "status": "active",
            "last_heartbeat": datetime.utcnow().isoformat()
        }


@router.get("/", response_model=List[DeviceResponse])
async def list_devices(
    user_id: UUID = Depends(verify_device),
    active_only: bool = True,
    limit: int = 50
):
    """List all devices for a user"""
    
    from sqlalchemy import select, and_
    
    async with AsyncSessionLocal() as session:
        query = select(DeviceSyncState).where(DeviceSyncState.user_id == user_id)
        
        if active_only:
            query = query.where(DeviceSyncState.is_active == True)
        
        query = query.limit(limit)
        
        result = await session.execute(query)
        devices = result.scalars().all()
        
        return [
            DeviceResponse(
                id=device.id,
                device_id=device.device_id,
                user_id=device.user_id,
                device_model=device.device_model,
                os_version=device.os_version,
                app_version=device.app_version,
                supports_edge_inference=device.supports_edge_inference,
                is_active=device.is_active,
                last_heartbeat=device.last_heartbeat,
                created_at=device.created_at
            )
            for device in devices
        ]


@router.get("/{device_id}", response_model=DeviceResponse)
async def get_device(
    device_id: str,
    user_id: UUID = Depends(verify_device)
):
    """Get device details"""
    
    from sqlalchemy import select
    
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(DeviceSyncState).where(
                DeviceSyncState.device_id == device_id,
                DeviceSyncState.user_id == user_id
            )
        )
        device = result.scalar_one_or_none()
        
        if not device:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Device not found"
            )
        
        return DeviceResponse(
            id=device.id,
            device_id=device.device_id,
            user_id=device.user_id,
            device_model=device.device_model,
            os_version=device.os_version,
            app_version=device.app_version,
            supports_edge_inference=device.supports_edge_inference,
            is_active=device.is_active,
            last_heartbeat=device.last_heartbeat,
            created_at=device.created_at
        )


@router.delete("/{device_id}")
async def unregister_device(
    device_id: str,
    user_id: UUID = Depends(verify_device)
):
    """Unregister a device"""
    
    from sqlalchemy import select, update
    
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(DeviceSyncState).where(
                DeviceSyncState.device_id == device_id,
                DeviceSyncState.user_id == user_id
            )
        )
        device = result.scalar_one_or_none()
        
        if not device:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Device not found"
            )
        
        # Soft delete
        await session.execute(
            update(DeviceSyncState)
            .where(DeviceSyncState.device_id == device_id)
            .values(is_active=False)
        )
        
        await session.commit()
        
        return {"message": f"Device {device_id} unregistered successfully"}