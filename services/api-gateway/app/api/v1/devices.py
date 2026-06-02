# services/api-gateway/app/api/v1/devices.py
"""Device management API endpoints"""

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from uuid import UUID
from typing import List, Optional

from ...schemas.devices import (
    DeviceRegister,
    DeviceResponse,
    DeviceUpdate,
    TelemetryData
)
from ...core.dependencies import get_current_active_user

router = APIRouter()


@router.post("/register", response_model=DeviceResponse)
async def register_device(
    device_data: DeviceRegister,
    current_user = Depends(get_current_active_user)
):
    """Register a new device for the user"""
    try:
        # Check if device already exists
        existing_device = await device_service.get_device_by_id(device_data.device_id)
        if existing_device:
            raise HTTPException(
                status_code=400,
                detail="Device already registered"
            )
        
        # Register device
        device = await device_service.register_device(
            user_id=current_user["id"],
            device_data=device_data
        )
        
        return device
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Device registration failed: {str(e)}"
        )


@router.get("/", response_model=List[DeviceResponse])
async def list_devices(
    current_user = Depends(get_current_active_user)
):
    """List all devices for current user"""
    try:
        devices = await device_service.get_user_devices(current_user["id"])
        return devices
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to list devices: {str(e)}"
        )


@router.get("/{device_id}", response_model=DeviceResponse)
async def get_device(
    device_id: UUID,
    current_user = Depends(get_current_active_user)
):
    """Get device details"""
    try:
        device = await device_service.get_device(device_id)
        
        if not device:
            raise HTTPException(status_code=404, detail="Device not found")
        
        if device["user_id"] != current_user["id"] and current_user["role"] != "admin":
            raise HTTPException(status_code=403, detail="Access denied")
        
        return device
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get device: {str(e)}"
        )


@router.put("/{device_id}", response_model=DeviceResponse)
async def update_device(
    device_id: UUID,
    device_update: DeviceUpdate,
    current_user = Depends(get_current_active_user)
):
    """Update device information"""
    try:
        device = await device_service.get_device(device_id)
        
        if not device:
            raise HTTPException(status_code=404, detail="Device not found")
        
        if device["user_id"] != current_user["id"] and current_user["role"] != "admin":
            raise HTTPException(status_code=403, detail="Access denied")
        
        updated = await device_service.update_device(device_id, device_update)
        
        return updated
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to update device: {str(e)}"
        )


@router.delete("/{device_id}")
async def delete_device(
    device_id: UUID,
    current_user = Depends(get_current_active_user)
):
    """Delete/unregister device"""
    try:
        device = await device_service.get_device(device_id)
        
        if not device:
            raise HTTPException(status_code=404, detail="Device not found")
        
        if device["user_id"] != current_user["id"] and current_user["role"] != "admin":
            raise HTTPException(status_code=403, detail="Access denied")
        
        await device_service.delete_device(device_id)
        
        return {"message": "Device deleted successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to delete device: {str(e)}"
        )


@router.post("/{device_id}/telemetry")
async def submit_telemetry(
    device_id: UUID,
    telemetry: TelemetryData,
    background_tasks: BackgroundTasks,
    current_user = Depends(get_current_active_user)
):
    """Submit device telemetry data"""
    try:
        # Verify device ownership
        device = await device_service.get_device(device_id)
        
        if not device:
            raise HTTPException(status_code=404, detail="Device not found")
        
        if device["user_id"] != current_user["id"] and current_user["role"] != "admin":
            raise HTTPException(status_code=403, detail="Access denied")
        
        # Process telemetry in background
        background_tasks.add_task(
            device_service.process_telemetry,
            device_id=device_id,
            telemetry=telemetry
        )
        
        return {"message": "Telemetry submitted successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to submit telemetry: {str(e)}"
        )


@router.post("/{device_id}/heartbeat")
async def device_heartbeat(
    device_id: UUID,
    current_user = Depends(get_current_active_user)
):
    """Update device last heartbeat timestamp"""
    try:
        await device_service.update_heartbeat(device_id)
        
        return {"message": "Heartbeat updated"}
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to update heartbeat: {str(e)}"
        )