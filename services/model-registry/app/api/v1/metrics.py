# services/model-registry/app/api/v1/metrics.py
"""Model metrics and monitoring endpoints"""

from fastapi import APIRouter, Depends, HTTPException, status
from typing import List, Optional
from datetime import datetime, timedelta
from uuid import UUID

from ...core.registry import ModelRegistry
from ...database import AsyncSessionLocal, ModelMetric, ModelVersion
from ...schemas import MetricCreate, MetricResponse

router = APIRouter()
registry = ModelRegistry()


@router.post("/{model_id}/metrics", response_model=MetricResponse)
async def record_metrics(
    model_id: UUID,
    metrics: MetricCreate
):
    """Record performance metrics for a model"""
    
    from sqlalchemy import select
    
    async with AsyncSessionLocal() as session:
        # Verify model exists
        result = await session.execute(
            select(ModelVersion).where(ModelVersion.id == model_id)
        )
        model = result.scalar_one_or_none()
        
        if not model:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Model not found"
            )
        
        # Create metrics record
        metric = ModelMetric(
            model_id=model_id,
            accuracy=metrics.accuracy,
            precision=metrics.precision,
            recall=metrics.recall,
            f1_score=metrics.f1_score,
            latency_p50=metrics.latency_p50,
            latency_p95=metrics.latency_p95,
            latency_p99=metrics.latency_p99,
            throughput=metrics.throughput,
            cpu_usage_percent=metrics.cpu_usage_percent,
            memory_usage_mb=metrics.memory_usage_mb,
            gpu_usage_percent=metrics.gpu_usage_percent,
            gpu_memory_mb=metrics.gpu_memory_mb,
            total_predictions=metrics.total_predictions or 0,
            successful_predictions=metrics.successful_predictions or 0,
            avg_confidence=metrics.avg_confidence,
            timestamp=datetime.utcnow()
        )
        
        session.add(metric)
        await session.commit()
        await session.refresh(metric)
        
        # Update model's best metrics if applicable
        if metrics.accuracy and (model.accuracy is None or metrics.accuracy > model.accuracy):
            model.accuracy = metrics.accuracy
            await session.commit()
        
        return metric


@router.get("/{model_id}/metrics", response_model=List[MetricResponse])
async def get_model_metrics(
    model_id: UUID,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    limit: int = 100
):
    """Get metrics history for a model"""
    
    from sqlalchemy import select, and_, desc
    
    async with AsyncSessionLocal() as session:
        query = select(ModelMetric).where(ModelMetric.model_id == model_id)
        
        if start_date:
            query = query.where(ModelMetric.timestamp >= start_date)
        if end_date:
            query = query.where(ModelMetric.timestamp <= end_date)
        
        query = query.order_by(desc(ModelMetric.timestamp)).limit(limit)
        
        result = await session.execute(query)
        metrics = result.scalars().all()
        
        return metrics


@router.get("/{model_id}/metrics/summary")
async def get_metrics_summary(
    model_id: UUID,
    hours: int = 24
):
    """Get aggregated metrics summary for a model"""
    
    from sqlalchemy import select, func, and_
    
    async with AsyncSessionLocal() as session:
        start_time = datetime.utcnow() - timedelta(hours=hours)
        
        # Get metrics in time range
        result = await session.execute(
            select(
                func.avg(ModelMetric.accuracy).label('avg_accuracy'),
                func.avg(ModelMetric.precision).label('avg_precision'),
                func.avg(ModelMetric.recall).label('avg_recall'),
                func.avg(ModelMetric.f1_score).label('avg_f1'),
                func.avg(ModelMetric.latency_p95).label('avg_latency_p95'),
                func.sum(ModelMetric.total_predictions).label('total_predictions'),
                func.avg(ModelMetric.avg_confidence).label('avg_confidence')
            )
            .where(
                and_(
                    ModelMetric.model_id == model_id,
                    ModelMetric.timestamp >= start_time
                )
            )
        )
        
        summary = result.first()
        
        if not summary or summary.total_predictions == 0:
            return {
                "model_id": str(model_id),
                "period_hours": hours,
                "total_predictions": 0,
                "message": "No metrics data available for this period"
            }
        
        return {
            "model_id": str(model_id),
            "period_hours": hours,
            "average_accuracy": float(summary.avg_accuracy) if summary.avg_accuracy else None,
            "average_precision": float(summary.avg_precision) if summary.avg_precision else None,
            "average_recall": float(summary.avg_recall) if summary.avg_recall else None,
            "average_f1_score": float(summary.avg_f1) if summary.avg_f1 else None,
            "average_latency_ms": float(summary.avg_latency_p95) if summary.avg_latency_p95 else None,
            "total_predictions": int(summary.total_predictions) if summary.total_predictions else 0,
            "average_confidence": float(summary.avg_confidence) if summary.avg_confidence else None
        }


@router.get("/models/compare")
async def compare_model_performance(
    model_ids: List[UUID],
    metric: str = "accuracy"
):
    """Compare performance of multiple models"""
    
    from sqlalchemy import select, desc
    from ...database import AsyncSessionLocal
    
    async with AsyncSessionLocal() as session:
        models_data = []
        
        for model_id in model_ids:
            # Get latest metrics
            result = await session.execute(
                select(ModelMetric)
                .where(ModelMetric.model_id == model_id)
                .order_by(desc(ModelMetric.timestamp))
                .limit(1)
            )
            latest_metrics = result.scalar_one_or_none()
            
            # Get model info
            model_result = await session.execute(
                select(ModelVersion).where(ModelVersion.id == model_id)
            )
            model = model_result.scalar_one_or_none()
            
            if model:
                models_data.append({
                    "model_id": str(model_id),
                    "version": model.version,
                    "model_type": model.model_type,
                    "status": model.status.value,
                    "latest_metrics": {
                        "accuracy": latest_metrics.accuracy if latest_metrics else model.accuracy,
                        "precision": latest_metrics.precision if latest_metrics else model.precision,
                        "recall": latest_metrics.recall if latest_metrics else model.recall,
                        "f1_score": latest_metrics.f1_score if latest_metrics else model.f1_score,
                        "latency_ms": latest_metrics.latency_p95 if latest_metrics else model.inference_time_ms,
                        "timestamp": latest_metrics.timestamp.isoformat() if latest_metrics else None
                    } if latest_metrics or model.accuracy else None
                })
        
        # Sort by specified metric
        if metric in ["accuracy", "precision", "recall", "f1_score"]:
            models_data.sort(
                key=lambda x: x.get("latest_metrics", {}).get(metric, 0) or 0,
                reverse=True
            )
        
        return {
            "comparison": models_data,
            "best_model": models_data[0]["version"] if models_data else None,
            "metric_used": metric
        }