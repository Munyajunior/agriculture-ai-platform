# services/analytics-service/app/schemas/alerts.py
"""Alert schemas."""

from typing import Any

from pydantic import BaseModel, Field


class AlertRule(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    alert_type: str
    condition: dict[str, Any]
    enabled: bool = True
    severity: str = "medium"
    notification_channels: list[str] = Field(default_factory=list)


class AlertNotification(BaseModel):
    id: str
    title: str
    message: str
    severity: str
    read: bool = False


class AlertAcknowledgement(BaseModel):
    notes: str | None = None
