# services/analytics-service/main.py
"""Analytics Service - Entry Point"""

"""Analytics Service - Main Entry Point"""

import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from prometheus_fastapi_instrumentator import Instrumentator

from app.config import settings
from app.api.v1 import api_router
from app.core.database import init_db, close_db
from app.core.cache import redis_client
from app.services.analytics_engine import AnalyticsEngine
from app.scheduler import start_scheduler, stop_scheduler

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Global instances
analytics_engine = AnalyticsEngine()

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager"""
    # Startup
    logger.info("Starting Analytics Service...")
    
    # Initialize database
    await init_db()
    logger.info("Database initialized")
    
    # Initialize Redis
    await redis_client.initialize()
    logger.info("Redis connection established")
    
    # Initialize analytics engine
    await analytics_engine.initialize()
    logger.info("Analytics engine initialized")
    
    # Start background scheduler
    start_scheduler()
    logger.info("Background scheduler started")
    
    yield
    
    # Shutdown
    logger.info("Shutting down Analytics Service...")
    stop_scheduler()
    await analytics_engine.close()
    await redis_client.close()
    await close_db()
    logger.info("Shutdown complete")

app = FastAPI(
    title="Agriculture AI Analytics Service",
    description="Analytics and reporting for plant disease detection platform",
    version="0.1.0",
    lifespan=lifespan
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Prometheus instrumentation
instrumentator = Instrumentator()
instrumentator.instrument(app).expose(app, endpoint="/metrics")

# Include routers
app.include_router(api_router, prefix="/api/v1")

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "analytics-service",
        "timestamp": datetime.utcnow().isoformat()
    }

@app.get("/ready")
async def readiness_check():
    """Readiness check endpoint"""
    db_ready = await check_db_connection()
    redis_ready = await redis_client.ping()
    
    return {
        "ready": db_ready and redis_ready,
        "database": db_ready,
        "redis": redis_ready
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8003,
        reload=settings.DEBUG
    )