# services/analytics-service/app/api/v1/alerts.py
"""Alert management endpoints"""

from typing import Optional, List
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from app.services.alert_service import AlertService
from app.core.auth import verify_token, require_role
from app.schemas.alerts import (
    AlertRule,
    AlertNotification,
    AlertAcknowledgement
)

router = APIRouter()
security = HTTPBearer()
alert_service = AlertService()


@router.get("/rules")
async def get_alert_rules(
    enabled_only: bool = True,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """Get alert rules"""
    user = await verify_token(credentials.credentials)
    
    rules = await alert_service.get_rules(
        user_id=user.id if user.role == "farmer" else None,
        enabled_only=enabled_only
    )
    
    return {"rules": rules, "total": len(rules)}


@router.post("/rules")
@require_role(["admin", "agronomist"])
async def create_alert_rule(
    rule: AlertRule,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """Create a new alert rule"""
    user = await verify_token(credentials.credentials)
    
    created_rule = await alert_service.create_rule(
        rule=rule,
        created_by=user.id
    )
    
    return created_rule


@router.put("/rules/{rule_id}")
@require_role(["admin", "agronomist"])
async def update_alert_rule(
    rule_id: str,
    rule: AlertRule,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """Update an existing alert rule"""
    user = await verify_token(credentials.credentials)
    
    updated_rule = await alert_service.update_rule(
        rule_id=rule_id,
        rule=rule,
        updated_by=user.id
    )
    
    if not updated_rule:
        raise HTTPException(status_code=404, detail="Alert rule not found")
    
    return updated_rule


@router.delete("/rules/{rule_id}")
@require_role(["admin"])
async def delete_alert_rule(
    rule_id: str,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """Delete an alert rule"""
    user = await verify_token(credentials.credentials)
    
    deleted = await alert_service.delete_rule(rule_id)
    
    if not deleted:
        raise HTTPException(status_code=404, detail="Alert rule not found")
    
    return {"message": "Alert rule deleted successfully"}


@router.get("/notifications")
async def get_notifications(
    limit: int = 50,
    offset: int = 0,
    unread_only: bool = False,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """Get user notifications"""
    user = await verify_token(credentials.credentials)
    
    notifications = await alert_service.get_notifications(
        user_id=user.id,
        limit=limit,
        offset=offset,
        unread_only=unread_only
    )
    
    return {
        "notifications": notifications,
        "total": len(notifications),
        "limit": limit,
        "offset": offset
    }


@router.post("/notifications/{notification_id}/acknowledge")
async def acknowledge_alert(
    notification_id: str,
    acknowledgement: AlertAcknowledgement,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """Acknowledge an alert notification"""
    user = await verify_token(credentials.credentials)
    
    result = await alert_service.acknowledge_alert(
        notification_id=notification_id,
        user_id=user.id,
        notes=acknowledgement.notes
    )
    
    if not result:
        raise HTTPException(status_code=404, detail="Notification not found")
    
    return {"message": "Alert acknowledged successfully"}


@router.post("/notifications/mark-read")
async def mark_notifications_read(
    notification_ids: List[str],
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """Mark multiple notifications as read"""
    user = await verify_token(credentials.credentials)
    
    count = await alert_service.mark_as_read(
        notification_ids=notification_ids,
        user_id=user.id
    )
    
    return {"message": f"{count} notifications marked as read"}


@router.get("/check")
async def check_alerts(
    background_tasks: BackgroundTasks,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """Manually trigger alert checking"""
    user = await verify_token(credentials.credentials)
    
    background_tasks.add_task(alert_service.check_alerts, user.id)
    
    return {"message": "Alert check initiated"}