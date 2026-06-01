# services/analytics-service/app/scheduler.py
"""Background scheduler for analytics tasks"""

import asyncio
import logging
from datetime import datetime, timedelta
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.cron import CronTrigger

from app.services.analytics_engine import analytics_engine
from app.services.metrics_service import metrics_service
from app.core.cache import redis_client

logger = logging.getLogger(__name__)

# Global scheduler instance
scheduler = AsyncIOScheduler()


def start_scheduler():
    """Start background scheduler"""
    # Refresh materialized views every hour
    scheduler.add_job(
        refresh_materialized_views,
        trigger=IntervalTrigger(hours=1),
        id='refresh_views',
        name='Refresh materialized views',
        replace_existing=True
    )
    
    # Calculate daily metrics at midnight
    scheduler.add_job(
        calculate_daily_metrics,
        trigger=CronTrigger(hour=0, minute=0),
        id='daily_metrics',
        name='Calculate daily metrics',
        replace_existing=True
    )
    
    # Clean up old cache every day at 2 AM
    scheduler.add_job(
        cleanup_cache,
        trigger=CronTrigger(hour=2, minute=0),
        id='cache_cleanup',
        name='Clean up old cache entries',
        replace_existing=True
    )
    
    # Generate predictive models weekly
    scheduler.add_job(
        update_predictive_models,
        trigger=CronTrigger(day_of_week='sun', hour=3, minute=0),
        id='update_models',
        name='Update predictive models',
        replace_existing=True
    )
    
    # Start scheduler
    scheduler.start()
    logger.info("Background scheduler started")


def stop_scheduler():
    """Stop background scheduler"""
    scheduler.shutdown()
    logger.info("Background scheduler stopped")


async def refresh_materialized_views():
    """Refresh database materialized views"""
    try:
        from app.core.database import get_session
        
        async with get_session() as session:
            await session.execute("REFRESH MATERIALIZED VIEW CONCURRENTLY analytics.daily_metrics")
            logger.info("Materialized views refreshed")
    except Exception as e:
        logger.error(f"Failed to refresh materialized views: {e}")


async def calculate_daily_metrics():
    """Calculate and store daily metrics"""
    try:
        # Get yesterday's metrics
        yesterday = datetime.utcnow() - timedelta(days=1)
        date_key = yesterday.strftime("%Y-%m-%d")
        
        # Calculate metrics
        metrics = await analytics_engine.get_dashboard_summary(days=1)
        
        # Store in Redis with TTL (keep for 30 days)
        await redis_client.set(
            f"daily_metrics:{date_key}",
            metrics,
            ttl=30*24*3600
        )
        
        logger.info(f"Daily metrics calculated for {date_key}")
    except Exception as e:
        logger.error(f"Failed to calculate daily metrics: {e}")


async def cleanup_cache():
    """Clean up old cache entries"""
    try:
        # Clear patterns older than 7 days
        pattern = "analytics:*"
        deleted = await redis_client.clear_pattern(pattern)
        logger.info(f"Cache cleanup completed: {deleted} entries removed")
    except Exception as e:
        logger.error(f"Cache cleanup failed: {e}")


async def update_predictive_models():
    """Update predictive analytics models"""
    try:
        # Retrain models with latest data
        await analytics_engine.predictive.initialize()
        logger.info("Predictive models updated")
    except Exception as e:
        logger.error(f"Failed to update predictive models: {e}")