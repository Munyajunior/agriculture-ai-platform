# services/analytics-service/app/services/metrics_service.py
"""Real-time metrics collection and aggregation service"""

import logging
import asyncio
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from collections import defaultdict
from dataclasses import dataclass, asdict
from prometheus_client import Counter, Histogram, Gauge, generate_latest
import psutil
import platform

from app.core.cache import redis_client
from app.core.database import get_session
from agriculture_ai.types.models import Scan, Prediction, User, Device

logger = logging.getLogger(__name__)

# Prometheus metrics
PREDICTIONS_TOTAL = Counter('predictions_total', 'Total number of predictions', ['source', 'status'])
INFERENCE_TIME = Histogram('inference_time_seconds', 'Inference time in seconds', ['source'])
ACTIVE_USERS = Gauge('active_users', 'Number of active users')
MODEL_ACCURACY = Gauge('model_accuracy', 'Current model accuracy', ['version'])
SYNC_QUEUE_SIZE = Gauge('sync_queue_size', 'Size of offline sync queue')


@dataclass
class SystemMetrics:
    """System performance metrics"""
    cpu_usage: float
    memory_usage: float
    disk_usage: float
    network_io: Dict[str, int]
    uptime_seconds: float
    timestamp: datetime


@dataclass
class BusinessMetrics:
    """Business KPIs"""
    total_scans: int
    total_predictions: int
    unique_users: int
    avg_confidence: float
    edge_vs_cloud_ratio: float
    success_rate: float
    timestamp: datetime


class MetricsService:
    """Service for collecting and managing platform metrics"""
    
    def __init__(self):
        self.start_time = datetime.utcnow()
        self._metrics_buffer = []
        self._buffer_size = 1000
        self._aggregation_window = 60  # seconds
        
    async def record_prediction(
        self,
        source: str,
        status: str,
        inference_time_ms: float,
        confidence: float
    ):
        """Record prediction metrics"""
        # Update Prometheus metrics
        PREDICTIONS_TOTAL.labels(source=source, status=status).inc()
        INFERENCE_TIME.labels(source=source).observe(inference_time_ms / 1000.0)
        
        # Store in buffer for aggregation
        self._metrics_buffer.append({
            "timestamp": datetime.utcnow(),
            "source": source,
            "status": status,
            "inference_time_ms": inference_time_ms,
            "confidence": confidence
        })
        
        # Flush if buffer is full
        if len(self._metrics_buffer) >= self._buffer_size:
            await self._flush_buffer()
    
    async def update_active_users(self, count: int):
        """Update active users gauge"""
        ACTIVE_USERS.set(count)
        
        # Store in Redis for historical tracking
        await redis_client.set(
            f"metrics:active_users:{datetime.utcnow().strftime('%Y-%m-%d-%H')}",
            count,
            ttl=86400  # 24 hours
        )
    
    async def update_model_accuracy(self, version: str, accuracy: float):
        """Update model accuracy metrics"""
        MODEL_ACCURACY.labels(version=version).set(accuracy)
    
    async def update_sync_queue(self, size: int):
        """Update sync queue size metric"""
        SYNC_QUEUE_SIZE.set(size)
    
    async def get_realtime_metrics(self) -> Dict[str, Any]:
        """Get real-time platform metrics"""
        # Get system metrics
        system_metrics = await self._get_system_metrics()
        
        # Get recent activity (last 5 minutes)
        recent_activity = await self._get_recent_activity(minutes=5)
        
        # Get current rate metrics
        rates = await self._get_current_rates()
        
        # Get queue status
        queue_status = await self._get_queue_status()
        
        return {
            "system": asdict(system_metrics),
            "activity": recent_activity,
            "rates": rates,
            "queue": queue_status,
            "timestamp": datetime.utcnow().isoformat()
        }
    
    async def get_user_activity(
        self,
        days: int = 7,
        activity_type: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get user activity metrics"""
        async with get_session() as session:
            start_date = datetime.utcnow() - timedelta(days=days)
            
            # Total active users
            from sqlalchemy import select, func, distinct
            
            active_users_query = select(
                func.count(distinct(Scan.user_id))
            ).where(Scan.created_at >= start_date)
            
            active_users = (await session.execute(active_users_query)).scalar() or 0
            
            # New users in period
            new_users_query = select(
                func.count(User.id)
            ).where(User.created_at >= start_date)
            
            new_users = (await session.execute(new_users_query)).scalar() or 0
            
            # Scans and predictions per user
            total_scans = await session.execute(
                select(func.count(Scan.id)).where(Scan.created_at >= start_date)
            )
            total_scans = total_scans.scalar() or 0
            
            scans_per_user = total_scans / active_users if active_users > 0 else 0
            
            # Top users by activity
            top_users_query = select(
                Scan.user_id,
                User.username,
                func.count(Scan.id).label("scan_count")
            ).join(User, Scan.user_id == User.id).where(
                Scan.created_at >= start_date
            ).group_by(Scan.user_id, User.username).order_by(
                func.count(Scan.id).desc()
            ).limit(10)
            
            top_users_result = await session.execute(top_users_query)
            top_users = []
            for row in top_users_result:
                top_users.append({
                    "user_id": str(row.user_id),
                    "username": row.username,
                    "scan_count": row.scan_count
                })
            
            # Activity timeline
            timeline = await self._get_activity_timeline(session, start_date, days)
            
            return {
                "total_active_users": active_users,
                "new_users": new_users,
                "scans_per_user": round(scans_per_user, 2),
                "predictions_per_user": round(scans_per_user, 2),  # One prediction per scan
                "top_users": top_users,
                "activity_timeline": timeline,
                "period_days": days
            }
    
    async def get_performance_breakdown(
        self,
        time_range: str = "24h"
    ) -> Dict[str, Any]:
        """Get detailed performance breakdown"""
        # Parse time range
        if time_range == "1h":
            minutes = 60
        elif time_range == "24h":
            minutes = 1440
        elif time_range == "7d":
            minutes = 10080
        else:
            minutes = 43200  # 30d
        
        start_time = datetime.utcnow() - timedelta(minutes=minutes)
        
        # Get metrics from Redis or compute from buffer
        cached_metrics = await redis_client.get(f"performance:{time_range}")
        if cached_metrics:
            return cached_metrics
        
        # Compute performance metrics
        metrics = await self._compute_performance_metrics(start_time)
        
        # Cache for 5 minutes
        await redis_client.set(f"performance:{time_range}", metrics, ttl=300)
        
        return metrics
    
    async def get_health_status(self) -> Dict[str, Any]:
        """Get overall system health status"""
        # Check service health
        services = await self._check_services_health()
        
        # Check database
        db_healthy = await self._check_database_health()
        
        # Check Redis
        redis_healthy = await redis_client.ping()
        
        # Check system resources
        system_metrics = await self._get_system_metrics()
        
        # Determine overall status
        critical_issues = []
        warnings = []
        
        if not db_healthy:
            critical_issues.append("Database connection failed")
        if not redis_healthy:
            critical_issues.append("Redis connection failed")
        if system_metrics.cpu_usage > 90:
            warnings.append(f"High CPU usage: {system_metrics.cpu_usage}%")
        if system_metrics.memory_usage > 90:
            warnings.append(f"High memory usage: {system_metrics.memory_usage}%")
        
        status = "healthy"
        if critical_issues:
            status = "critical"
        elif warnings:
            status = "degraded"
        
        return {
            "status": status,
            "timestamp": datetime.utcnow().isoformat(),
            "services": services,
            "database": db_healthy,
            "redis": redis_healthy,
            "system": asdict(system_metrics),
            "issues": {
                "critical": critical_issues,
                "warnings": warnings
            }
        }
    
    async def _flush_buffer(self):
        """Flush metrics buffer to storage"""
        if not self._metrics_buffer:
            return
        
        # Aggregate metrics by minute
        aggregated = defaultdict(lambda: {
            "count": 0,
            "total_inference_time": 0,
            "total_confidence": 0,
            "sources": defaultdict(int),
            "statuses": defaultdict(int)
        })
        
        for metric in self._metrics_buffer:
            minute_key = metric["timestamp"].strftime("%Y-%m-%d-%H-%M")
            agg = aggregated[minute_key]
            agg["count"] += 1
            agg["total_inference_time"] += metric["inference_time_ms"]
            agg["total_confidence"] += metric["confidence"]
            agg["sources"][metric["source"]] += 1
            agg["statuses"][metric["status"]] += 1
        
        # Store aggregated metrics in Redis
        for minute_key, agg in aggregated.items():
            await redis_client.set(
                f"metrics:minute:{minute_key}",
                {
                    "count": agg["count"],
                    "avg_inference_time": agg["total_inference_time"] / agg["count"],
                    "avg_confidence": agg["total_confidence"] / agg["count"],
                    "sources": dict(agg["sources"]),
                    "statuses": dict(agg["statuses"])
                },
                ttl=86400  # 24 hours
            )
        
        # Clear buffer
        self._metrics_buffer.clear()
    
    async def _get_system_metrics(self) -> SystemMetrics:
        """Get system metrics"""
        # CPU usage
        cpu_usage = psutil.cpu_percent(interval=1)
        
        # Memory usage
        memory = psutil.virtual_memory()
        memory_usage = memory.percent
        
        # Disk usage
        disk = psutil.disk_usage('/')
        disk_usage = disk.percent
        
        # Network I/O
        net_io = psutil.net_io_counters()
        network_io = {
            "bytes_sent": net_io.bytes_sent,
            "bytes_recv": net_io.bytes_recv,
            "packets_sent": net_io.packets_sent,
            "packets_recv": net_io.packets_recv
        }
        
        # Uptime
        uptime_seconds = (datetime.utcnow() - self.start_time).total_seconds()
        
        return SystemMetrics(
            cpu_usage=cpu_usage,
            memory_usage=memory_usage,
            disk_usage=disk_usage,
            network_io=network_io,
            uptime_seconds=uptime_seconds,
            timestamp=datetime.utcnow()
        )
    
    async def _get_recent_activity(self, minutes: int = 5) -> Dict[str, Any]:
        """Get recent activity metrics"""
        start_time = datetime.utcnow() - timedelta(minutes=minutes)
        
        # Get from Redis metrics
        total_predictions = 0
        avg_confidence = 0.0
        
        for i in range(minutes):
            minute_key = (start_time + timedelta(minutes=i)).strftime("%Y-%m-%d-%H-%M")
            metric = await redis_client.get(f"metrics:minute:{minute_key}")
            
            if metric:
                total_predictions += metric.get("count", 0)
                avg_confidence += metric.get("avg_confidence", 0) * metric.get("count", 0)
        
        if total_predictions > 0:
            avg_confidence /= total_predictions
        
        return {
            "total_predictions": total_predictions,
            "avg_confidence": round(avg_confidence, 3),
            "period_minutes": minutes,
            "predictions_per_minute": round(total_predictions / minutes, 2)
        }
    
    async def _get_current_rates(self) -> Dict[str, Any]:
        """Get current rates (per second, per minute)"""
        # Get last 5 minutes of data
        last_5_min = await self._get_recent_activity(minutes=5)
        
        # Calculate rates
        predictions_per_second = last_5_min["total_predictions"] / 300  # 5 minutes = 300 seconds
        predictions_per_minute = last_5_min["predictions_per_minute"]
        
        return {
            "predictions_per_second": round(predictions_per_second, 2),
            "predictions_per_minute": round(predictions_per_minute, 2),
            "active_sessions": await self._get_active_sessions_count()
        }
    
    async def _get_queue_status(self) -> Dict[str, Any]:
        """Get queue status"""
        # Get sync queue size from Redis
        sync_queue_size = await redis_client.get("sync:queue:size") or 0
        
        # Get pending sync items
        pending_sync = await redis_client.get("sync:pending:count") or 0
        
        return {
            "sync_queue_size": int(sync_queue_size),
            "pending_sync_items": int(pending_sync),
            "processing_rate": await self._get_processing_rate()
        }
    
    async def _get_activity_timeline(
        self,
        session,
        start_date: datetime,
        days: int
    ) -> List[Dict[str, Any]]:
        """Get activity timeline data"""
        from sqlalchemy import select, func
        
        timeline = []
        
        for i in range(days):
            day_start = start_date + timedelta(days=i)
            day_end = day_start + timedelta(days=1)
            
            # Count scans for this day
            scans_query = select(func.count(Scan.id)).where(
                Scan.created_at >= day_start,
                Scan.created_at < day_end
            )
            scans_count = (await session.execute(scans_query)).scalar() or 0
            
            # Count unique users for this day
            users_query = select(
                func.count(func.distinct(Scan.user_id))
            ).where(
                Scan.created_at >= day_start,
                Scan.created_at < day_end
            )
            users_count = (await session.execute(users_query)).scalar() or 0
            
            timeline.append({
                "date": day_start.strftime("%Y-%m-%d"),
                "scans": scans_count,
                "unique_users": users_count
            })
        
        return timeline
    
    async def _compute_performance_metrics(self, start_time: datetime) -> Dict[str, Any]:
        """Compute detailed performance metrics"""
        async with get_session() as session:
            from sqlalchemy import select, func
            
            # Get average inference time
            avg_time_query = select(
                func.avg(Prediction.processing_time_ms)
            ).where(
                Prediction.created_at >= start_time,
                Prediction.processing_time_ms.isnot(None)
            )
            avg_time = (await session.execute(avg_time_query)).scalar() or 0
            
            # Get confidence distribution
            confidence_distribution = {
                "high": 0,  # > 0.8
                "medium": 0,  # 0.5 - 0.8
                "low": 0  # < 0.5
            }
            
            for bucket, (low, high) in [
                ("high", (0.8, 1.0)),
                ("medium", (0.5, 0.8)),
                ("low", (0.0, 0.5))
            ]:
                count_query = select(func.count(Prediction.id)).where(
                    Prediction.created_at >= start_time,
                    Prediction.confidence_score >= low,
                    Prediction.confidence_score < high
                )
                confidence_distribution[bucket] = (await session.execute(count_query)).scalar() or 0
            
            # Get success rate (predictions with confidence > 0.7)
            total_query = select(func.count(Prediction.id)).where(
                Prediction.created_at >= start_time
            )
            total = (await session.execute(total_query)).scalar() or 1
            
            success_query = select(func.count(Prediction.id)).where(
                Prediction.created_at >= start_time,
                Prediction.confidence_score > 0.7
            )
            successful = (await session.execute(success_query)).scalar() or 0
            success_rate = successful / total
            
            # Get inference source breakdown
            source_query = select(
                Prediction.inference_source,
                func.count(Prediction.id)
            ).where(
                Prediction.created_at >= start_time
            ).group_by(Prediction.inference_source)
            
            source_breakdown = {}
            source_results = await session.execute(source_query)
            for row in source_results:
                source_breakdown[row[0]] = row[1]
            
            # Get processing time percentiles
            times_query = select(Prediction.processing_time_ms).where(
                Prediction.created_at >= start_time,
                Prediction.processing_time_ms.isnot(None)
            ).order_by(Prediction.processing_time_ms).limit(1000)
            
            times = (await session.execute(times_query)).scalars().all()
            
            percentiles = {}
            if times:
                sorted_times = sorted(times)
                percentiles = {
                    "p50": sorted_times[len(sorted_times) // 2],
                    "p90": sorted_times[int(len(sorted_times) * 0.9)],
                    "p95": sorted_times[int(len(sorted_times) * 0.95)],
                    "p99": sorted_times[int(len(sorted_times) * 0.99)]
                }
            
            return {
                "average_processing_time_ms": round(float(avg_time), 2),
                "confidence_distribution": confidence_distribution,
                "success_rate": round(success_rate, 3),
                "inference_source_breakdown": source_breakdown,
                "processing_time_percentiles": percentiles,
                "total_predictions": total,
                "time_range_minutes": int((datetime.utcnow() - start_time).total_seconds() / 60)
            }
    
    async def _check_services_health(self) -> Dict[str, bool]:
        """Check health of dependent services"""
        services = {}
        
        # Check API Gateway
        try:
            import aiohttp
            async with aiohttp.ClientSession() as session:
                async with session.get("http://api-gateway:8000/health") as resp:
                    services["api_gateway"] = resp.status == 200
        except:
            services["api_gateway"] = False
        
        # Check AI Service
        try:
            import aiohttp
            async with aiohttp.ClientSession() as session:
                async with session.get("http://ai-service:8002/health") as resp:
                    services["ai_service"] = resp.status == 200
        except:
            services["ai_service"] = False
        
        return services
    
    async def _check_database_health(self) -> bool:
        """Check database connectivity"""
        try:
            async with get_session() as session:
                await session.execute("SELECT 1")
                return True
        except:
            return False
    
    async def _get_active_sessions_count(self) -> int:
        """Get number of active user sessions"""
        # This would typically come from Redis session store
        session_keys = await redis_client.client.keys("session:*")
        return len(session_keys) if session_keys else 0
    
    async def _get_processing_rate(self) -> float:
        """Get current processing rate (predictions per second)"""
        rates = await self._get_current_rates()
        return rates.get("predictions_per_second", 0)


metrics_service = MetricsService()
