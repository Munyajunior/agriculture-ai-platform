# services/ai-service/app/api/v1/health.py
"""Health check API endpoints"""

from fastapi import APIRouter, Depends
from datetime import datetime
import asyncio
import torch

from ...core.inference_engine import inference_engine
from ...core.database import get_db
from ...config import settings

router = APIRouter()


@router.get("/")
async def health_check():
    """
    Basic health check
    """
    return {
        "status": "healthy",
        "service": "ai-service",
        "timestamp": datetime.utcnow().isoformat(),
        "version": "0.1.0"
    }


@router.get("/detailed")
async def detailed_health_check(db = Depends(get_db)):
    """
    Detailed health check with component statuses
    """
    components = {}
    
    # Check inference engine
    try:
        components["inference_engine"] = {
            "status": "healthy" if inference_engine.is_loaded else "degraded",
            "model_loaded": inference_engine.is_loaded,
            "device": str(inference_engine.device) if hasattr(inference_engine, 'device') else "unknown",
            "model_config": inference_engine.model_config if hasattr(inference_engine, 'model_config') else None
        }
    except Exception as e:
        components["inference_engine"] = {
            "status": "unhealthy",
            "error": str(e)
        }
    
    # Check database
    try:
        # Simple query to test connection
        from sqlalchemy import text
        result = await db.execute(text("SELECT 1"))
        await db.commit()
        
        components["database"] = {
            "status": "healthy",
            "type": "postgresql"
        }
    except Exception as e:
        components["database"] = {
            "status": "unhealthy",
            "error": str(e)
        }
    
    # Check GPU if available
    if torch.cuda.is_available():
        try:
            components["gpu"] = {
                "status": "healthy",
                "device_name": torch.cuda.get_device_name(0),
                "memory_allocated_mb": torch.cuda.memory_allocated(0) / (1024 ** 2),
                "memory_cached_mb": torch.cuda.memory_reserved(0) / (1024 ** 2)
            }
        except Exception as e:
            components["gpu"] = {
                "status": "degraded",
                "error": str(e)
            }
    else:
        components["gpu"] = {
            "status": "not_available",
            "message": "No GPU detected, using CPU"
        }
    
    # Check Redis (if configured)
    if settings.REDIS_URL:
        try:
            import redis.asyncio as redis
            redis_client = redis.from_url(settings.REDIS_URL)
            await redis_client.ping()
            await redis_client.close()
            
            components["redis"] = {
                "status": "healthy"
            }
        except Exception as e:
            components["redis"] = {
                "status": "unhealthy",
                "error": str(e)
            }
    
    # Overall status
    unhealthy = any(c.get("status") == "unhealthy" for c in components.values())
    degraded = any(c.get("status") == "degraded" for c in components.values())
    
    if unhealthy:
        overall_status = "unhealthy"
    elif degraded:
        overall_status = "degraded"
    else:
        overall_status = "healthy"
    
    return {
        "status": overall_status,
        "service": "ai-service",
        "timestamp": datetime.utcnow().isoformat(),
        "uptime_seconds": _get_uptime(),
        "components": components
    }


@router.get("/readiness")
async def readiness_check():
    """
    Readiness probe for Kubernetes
    """
    ready = inference_engine.is_loaded
    
    return {
        "ready": ready,
        "message": "Ready to serve requests" if ready else "Model not loaded"
    }


@router.get("/liveness")
async def liveness_check():
    """
    Liveness probe for Kubernetes
    """
    return {
        "alive": True,
        "timestamp": datetime.utcnow().isoformat()
    }


@router.get("/metrics")
async def get_metrics():
    """
    Get service metrics for Prometheus
    """
    metrics = {
        "model_loaded": 1 if inference_engine.is_loaded else 0,
        "device_type": "gpu" if torch.cuda.is_available() else "cpu",
        "timestamp": datetime.utcnow().isoformat()
    }
    
    if torch.cuda.is_available():
        metrics.update({
            "gpu_memory_used_mb": torch.cuda.memory_allocated(0) / (1024 ** 2),
            "gpu_memory_total_mb": torch.cuda.get_device_properties(0).total_memory / (1024 ** 2)
        })
    
    return metrics


def _get_uptime() -> float:
    """Get service uptime in seconds"""
    import time
    
    # This would need to track start time
    # For now, return a mock value
    return 3600.0
