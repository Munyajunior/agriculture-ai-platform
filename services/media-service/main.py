# services/media-service/main.py
"""Media Service - Main Entry Point"""

import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from prometheus_fastapi_instrumentator import Instrumentator

from app.config import settings
from app.api.v1 import api_router
from app.core.storage import StorageManager
from app.core.image_processor import ImageProcessor
from app.core.cache import CacheManager
from app.database import init_db
from app.workers.thumbnail_worker import thumbnail_worker
from app.middleware import RequestLoggingMiddleware

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize core components
storage_manager = StorageManager()
image_processor = ImageProcessor()
cache_manager = CacheManager()

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager"""
    # Startup
    logger.info("Starting Media Service...")
    
    # Initialize database
    await init_db()
    logger.info("Database initialized")
    
    # Initialize storage
    await storage_manager.initialize()
    logger.info("Storage initialized")
    
    # Initialize cache
    await cache_manager.initialize()
    logger.info("Cache initialized")
    
    # Start background workers
    await thumbnail_worker.start()
    logger.info("Background workers started")
    
    yield
    
    # Shutdown
    logger.info("Shutting down Media Service...")
    await thumbnail_worker.stop()
    await cache_manager.close()
    logger.info("Shutdown complete")

app = FastAPI(
    title="Agriculture AI Media Service",
    description="Image and media management for plant disease detection",
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json"
)

# Add middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=settings.ALLOWED_HOSTS,
)

app.add_middleware(RequestLoggingMiddleware)

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
        "service": "media-service",
        "storage": await storage_manager.health_check(),
        "cache": await cache_manager.health_check()
    }

@app.get("/ready")
async def readiness_check():
    """Readiness check endpoint"""
    storage_ready = await storage_manager.health_check()
    cache_ready = await cache_manager.health_check()
    database_ready = await init_db.health_check()
    
    return {
        "ready": storage_ready and cache_ready and database_ready,
        "services": {
            "storage": storage_ready,
            "cache": cache_ready,
            "database": database_ready
        }
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8004,
        reload=settings.DEBUG,
        log_level=settings.LOG_LEVEL.lower()
    )