# services/api-gateway/app/schemas/devices.py
"""Device schemas for gateway device routes."""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class DeviceRegister(BaseModel):
    device_name: str = Field(..., min_length=1, max_length=100)
    device_type: str
    device_id: str = Field(..., min_length=1, max_length=255)
    firmware_version: str | None = None
    capabilities: dict[str, Any] | None = None


class DeviceUpdate(BaseModel):
    device_name: str | None = Field(None, min_length=1, max_length=100)
    firmware_version: str | None = None
    capabilities: dict[str, Any] | None = None
    is_active: bool | None = None


class DeviceResponse(DeviceRegister):
    id: UUID
    user_id: UUID
    is_active: bool = True
    registered_at: datetime | None = None
    last_heartbeat: datetime | None = None


class TelemetryData(BaseModel):
    telemetry_type: str
    data: dict[str, Any]
    battery_level: float | None = Field(None, ge=0, le=100)
    signal_strength: int | None = None
    gps_latitude: float | None = Field(None, ge=-90, le=90)
    gps_longitude: float | None = Field(None, ge=-180, le=180)
    gps_altitude: float | None = None
    speed_kph: float | None = Field(None, ge=0)
