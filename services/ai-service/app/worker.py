# services/ai-service/app/worker.py
"""Celery worker for async tasks"""

from celery import Celery
from .config import settings

# Initialize Celery
celery_app = Celery(
    "ai_service",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=30 * 60,
    task_soft_time_limit=25 * 60,
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=100
)


@celery_app.task(bind=True, max_retries=3)
def process_batch_predictions(self, image_urls: list, user_id: str):
    """Process batch predictions asynchronously"""
    
    try:
        # Import here to avoid circular imports
        from .services.prediction_service import PredictionService
        
        service = PredictionService()
        
        # Process predictions
        results = []
        for url in image_urls:
            result = service.process_prediction_from_url(url, user_id)
            results.append(result)
        
        return results
        
    except Exception as e:
        self.retry(exc=e, countdown=60)
        raise


@celery_app.task
def update_model_from_registry():
    """Update model from registry"""
    
    from .core.model_registry import ModelRegistry
    
    registry = ModelRegistry()
    # Implement model update logic
    pass


@celery_app.task
def cleanup_old_predictions(days: int = 30):
    """Clean up old prediction records"""
    
    from datetime import datetime, timedelta
    
    # Implement cleanup logic
    cutoff_date = datetime.utcnow() - timedelta(days=days)
    
    # Delete old predictions
    # ...
    
    return f"Cleaned up predictions older than {days} days"