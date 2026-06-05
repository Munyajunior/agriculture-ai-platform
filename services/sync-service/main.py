# services/sync-service/main.py
"""Sync Service - Main Entry Point"""

import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from prometheus_fastapi_instrumentator import Instrumentator

from app.config import settings
from app.api.v1 import api_router
from app.core.sync_engine import SyncEngine
from app.core.conflict_resolver import ConflictResolver
from app.core.queue_manager import QueueManager
from app.database import init_db
from app.workers.sync_worker import sync_worker

logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize components
sync_engine = SyncEngine()
conflict_resolver = ConflictResolver()
queue_manager = QueueManager()

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager"""
    # Startup
    logger.info("Starting Sync Service...")
    
    # Initialize database
    await init_db()
    logger.info("Database initialized")
    
    # Initialize queue
    await queue_manager.initialize()
    logger.info("Queue manager initialized")
    
    # Initialize sync engine
    await sync_engine.initialize()
    logger.info("Sync engine initialized")
    
    # Start background workers
    await sync_worker.start()
    logger.info("Sync workers started")
    
    yield
    
    # Shutdown
    logger.info("Shutting down Sync Service...")
    await sync_worker.stop()
    await queue_manager.close()

app = FastAPI(
    title="Agriculture AI Sync Service",
    description="Offline-first synchronization for edge devices",
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json"
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Prometheus
instrumentator = Instrumentator()
instrumentator.instrument(app).expose(app, endpoint="/metrics")

# Include routers
app.include_router(api_router, prefix="/api/v1")

@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "service": "sync-service",
        "queue_size": await queue_manager.get_queue_size(),
        "active_syncs": sync_engine.active_syncs
    }

@app.get("/ready")
async def readiness_check():
    return {
        "ready": True,
        "database": True,
        "queue": await queue_manager.health_check()
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8006,
        reload=settings.DEBUG
    )