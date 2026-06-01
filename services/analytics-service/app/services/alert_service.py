# services/analytics-service/app/services/alert_service.py
"""Alert management service for proactive notifications"""

import logging
import json
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass
from enum import Enum
import asyncio

from app.core.cache import redis_client
from app.core.database import get_session
from shared.types.models import User, Scan, Prediction

logger = logging.getLogger(__name__)


class AlertSeverity(Enum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"
    EMERGENCY = "emergency"


class AlertType(Enum):
    DISEASE_OUTBREAK = "disease_outbreak"
    HIGH_RISK = "high_risk"
    LOW_CONFIDENCE = "low_confidence"
    SYSTEM_ISSUE = "system_issue"
    MODEL_UPDATE = "model_update"
    SYNC_FAILURE = "sync_failure"


@dataclass
class AlertRule:
    id: str
    name: str
    alert_type: AlertType
    severity: AlertSeverity
    condition: Dict[str, Any]
    enabled: bool
    created_by: str
    created_at: datetime
    recipients: List[str]


class AlertService:
    """Service for managing and sending alerts"""
    
    def __init__(self):
        self.rules_cache = {}
        self.notification_channels = ["email", "push", "webhook"]
        
    async def get_rules(
        self,
        user_id: Optional[str] = None,
        enabled_only: bool = True
    ) -> List[Dict[str, Any]]:
        """Get alert rules"""
        rules = []
        
        # Get from Redis cache
        cache_key = f"alert_rules:{user_id if user_id else 'all'}"
        cached_rules = await redis_client.get(cache_key)
        
        if cached_rules:
            return cached_rules
        
        # Default rules
        default_rules = [
            {
                "id": "rule_1",
                "name": "High Disease Risk",
                "alert_type": "high_risk",
                "severity": "critical",
                "condition": {
                    "risk_score": 0.7,
                    "operator": ">="
                },
                "enabled": True,
                "description": "Alert when disease risk score exceeds 70%"
            },
            {
                "id": "rule_2",
                "name": "Disease Outbreak Detection",
                "alert_type": "disease_outbreak",
                "severity": "emergency",
                "condition": {
                    "detection_rate": 10,
                    "time_window_hours": 24,
                    "operator": ">="
                },
                "enabled": True,
                "description": "Alert when 10+ detections in 24 hours"
            },
            {
                "id": "rule_3",
                "name": "Low Confidence Predictions",
                "alert_type": "low_confidence",
                "severity": "warning",
                "condition": {
                    "confidence_threshold": 0.5,
                    "min_predictions": 5
                },
                "enabled": True,
                "description": "Alert when multiple low-confidence predictions occur"
            }
        ]
        
        # Cache for 1 hour
        await redis_client.set(cache_key, default_rules, ttl=3600)
        
        return default_rules
    
    async def create_rule(
        self,
        rule: AlertRule,
        created_by: str
    ) -> Dict[str, Any]:
        """Create new alert rule"""
        rule_dict = {
            "id": rule.id,
            "name": rule.name,
            "alert_type": rule.alert_type.value,
            "severity": rule.severity.value,
            "condition": rule.condition,
            "enabled": rule.enabled,
            "created_by": created_by,
            "created_at": datetime.utcnow().isoformat(),
            "recipients": rule.recipients
        }
        
        # Store in Redis
        await redis_client.set(
            f"alert_rule:{rule.id}",
            rule_dict,
            ttl=30*24*3600  # 30 days
        )
        
        # Invalidate cache
        await redis_client.delete("alert_rules:all")
        
        return rule_dict
    
    async def update_rule(
        self,
        rule_id: str,
        rule: AlertRule,
        updated_by: str
    ) -> Optional[Dict[str, Any]]:
        """Update existing alert rule"""
        existing = await redis_client.get(f"alert_rule:{rule_id}")
        
        if not existing:
            return None
        
        updated_rule = {
            **existing,
            "name": rule.name,
            "alert_type": rule.alert_type.value,
            "severity": rule.severity.value,
            "condition": rule.condition,
            "enabled": rule.enabled,
            "updated_by": updated_by,
            "updated_at": datetime.utcnow().isoformat()
        }
        
        await redis_client.set(f"alert_rule:{rule_id}", updated_rule)
        await redis_client.delete("alert_rules:all")
        
        return updated_rule
    
    async def delete_rule(self, rule_id: str) -> bool:
        """Delete alert rule"""
        deleted = await redis_client.delete(f"alert_rule:{rule_id}")
        await redis_client.delete("alert_rules:all")
        return deleted > 0
    
    async def get_notifications(
        self,
        user_id: str,
        limit: int = 50,
        offset: int = 0,
        unread_only: bool = False
    ) -> List[Dict[str, Any]]:
        """Get notifications for user"""
        notifications_key = f"notifications:{user_id}"
        
        # Get from Redis (stored as list)
        notifications = await redis_client.client.lrange(
            notifications_key, offset, offset + limit - 1
        )
        
        result = []
        for notif in notifications:
            notif_dict = json.loads(notif)
            
            if unread_only and notif_dict.get("read", False):
                continue
                
            result.append(notif_dict)
        
        return result
    
    async def acknowledge_alert(
        self,
        notification_id: str,
        user_id: str,
        notes: Optional[str] = None
    ) -> bool:
        """Acknowledge an alert"""
        notif_key = f"notification:{notification_id}"
        
        notification = await redis_client.get(notif_key)
        
        if not notification:
            return False
        
        # Update notification
        notification["acknowledged"] = True
        notification["acknowledged_by"] = user_id
        notification["acknowledged_at"] = datetime.utcnow().isoformat()
        notification["acknowledgement_notes"] = notes
        
        await redis_client.set(notif_key, notification)
        
        return True
    
    async def mark_as_read(
        self,
        notification_ids: List[str],
        user_id: str
    ) -> int:
        """Mark notifications as read"""
        count = 0
        
        for notif_id in notification_ids:
            notif_key = f"notification:{notif_id}"
            notification = await redis_client.get(notif_key)
            
            if notification and notification.get("user_id") == user_id:
                notification["read"] = True
                notification["read_at"] = datetime.utcnow().isoformat()
                await redis_client.set(notif_key, notification)
                count += 1
        
        return count
    
    async def check_alerts(self, user_id: str):
        """Check for alerts based on rules"""
        rules = await self.get_rules(user_id=user_id, enabled_only=True)
        
        for rule in rules:
            await self._evaluate_rule(rule, user_id)
    
    async def _evaluate_rule(self, rule: Dict[str, Any], user_id: str):
        """Evaluate a rule against current metrics"""
        rule_type = rule["alert_type"]
        condition = rule["condition"]
        
        triggered = False
        alert_data = None
        
        if rule_type == "high_risk":
            triggered = await self._check_high_risk(condition)
            alert_data = {"risk_score": condition.get("risk_score", 0.7)}
            
        elif rule_type == "disease_outbreak":
            triggered, detection_rate = await self._check_outbreak(condition)
            alert_data = {"detection_rate": detection_rate}
            
        elif rule_type == "low_confidence":
            triggered, low_conf_count = await self._check_low_confidence(condition)
            alert_data = {"low_confidence_count": low_conf_count}
        
        if triggered:
            await self._send_alert(rule, user_id, alert_data)
    
    async def _check_high_risk(self, condition: Dict[str, Any]) -> bool:
        """Check if high risk threshold is exceeded"""
        # Get current risk score from analytics engine
        from app.services.analytics_engine import analytics_engine
        
        risk_assessment = await analytics_engine.assess_risk(pd.DataFrame())
        risk_score = risk_assessment.get("overall_risk_score", 0)
        
        threshold = condition.get("risk_score", 0.7)
        operator = condition.get("operator", ">=")
        
        if operator == ">=":
            return risk_score >= threshold
        elif operator == ">":
            return risk_score > threshold
        elif operator == "<=":
            return risk_score <= threshold
        
        return False
    
    async def _check_outbreak(self, condition: Dict[str, Any]) -> tuple:
        """Check for disease outbreak conditions"""
        time_window = condition.get("time_window_hours", 24)
        threshold = condition.get("detection_rate", 10)
        
        start_time = datetime.utcnow() - timedelta(hours=time_window)
        
        async with get_session() as session:
            from sqlalchemy import select, func
            
            count_query = select(func.count(Prediction.id)).where(
                Prediction.created_at >= start_time
            )
            
            result = await session.execute(count_query)
            detection_count = result.scalar() or 0
            
            return detection_count >= threshold, detection_count
    
    async def _check_low_confidence(self, condition: Dict[str, Any]) -> tuple:
        """Check for low confidence predictions"""
        confidence_threshold = condition.get("confidence_threshold", 0.5)
        min_predictions = condition.get("min_predictions", 5)
        
        start_time = datetime.utcnow() - timedelta(hours=24)
        
        async with get_session() as session:
            from sqlalchemy import select, func
            
            low_conf_count = await session.execute(
                select(func.count(Prediction.id)).where(
                    Prediction.created_at >= start_time,
                    Prediction.confidence_score < confidence_threshold
                )
            )
            count = low_conf_count.scalar() or 0
            
            return count >= min_predictions, count
    
    async def _send_alert(
        self,
        rule: Dict[str, Any],
        user_id: str,
        alert_data: Dict[str, Any]
    ):
        """Send alert to recipients"""
        # Create notification
        notification = {
            "id": self._generate_notification_id(),
            "user_id": user_id,
            "rule_id": rule["id"],
            "rule_name": rule["name"],
            "severity": rule["severity"],
            "alert_type": rule["alert_type"],
            "message": self._format_alert_message(rule, alert_data),
            "data": alert_data,
            "created_at": datetime.utcnow().isoformat(),
            "read": False,
            "acknowledged": False
        }
        
        # Store notification
        notif_key = f"notification:{notification['id']}"
        await redis_client.set(notif_key, notification, ttl=7*24*3600)  # 7 days
        
        # Add to user's notification list
        notifications_key = f"notifications:{user_id}"
        await redis_client.client.lpush(
            notifications_key,
            json.dumps(notification)
        )
        await redis_client.client.ltrim(notifications_key, 0, 99)  # Keep last 100
        
        # Send via configured channels
        for channel in self.notification_channels:
            await self._send_via_channel(channel, notification, rule.get("recipients", []))
        
        logger.info(f"Alert sent: {rule['name']} to user {user_id}")
    
    async def _send_via_channel(
        self,
        channel: str,
        notification: Dict[str, Any],
        recipients: List[str]
    ):
        """Send notification via specific channel"""
        try:
            if channel == "email" and recipients:
                # Implement email sending
                pass
            elif channel == "push":
                # Implement push notification
                pass
            elif channel == "webhook":
                # Implement webhook
                pass
        except Exception as e:
            logger.error(f"Failed to send via {channel}: {e}")
    
    def _format_alert_message(
        self,
        rule: Dict[str, Any],
        alert_data: Dict[str, Any]
    ) -> str:
        """Format alert message based on rule type"""
        if rule["alert_type"] == "high_risk":
            return f"High disease risk detected! Current risk score: {alert_data.get('risk_score', 0):.2f}"
        elif rule["alert_type"] == "disease_outbreak":
            return f"Disease outbreak detected! {alert_data.get('detection_rate', 0)} detections in 24 hours"
        elif rule["alert_type"] == "low_confidence":
            return f"Multiple low-confidence predictions: {alert_data.get('low_confidence_count', 0)} in 24 hours"
        else:
            return f"Alert: {rule['name']}"
    
    def _generate_notification_id(self) -> str:
        """Generate unique notification ID"""
        import uuid
        return str(uuid.uuid4())