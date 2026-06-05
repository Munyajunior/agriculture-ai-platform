# services/model-registry/main.py
"""Model Registry Service - Main Entry Point"""

import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from prometheus_fastapi_instrumentator import Instrumentator

from app.config import settings
from app.api.v1 import api_router
from app.core.registry import ModelRegistry
from app.core.model_manager import ModelManager
from app.core.storage import ModelStorage
from app.database import init_db
from app.monitoring import ModelMonitor

logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize components
model_registry = ModelRegistry()
model_manager = ModelManager()
model_storage = ModelStorage()
model_monitor = ModelMonitor()

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager"""
    # Startup
    logger.info("Starting Model Registry Service...")
    
    # Initialize database
    await init_db()
    logger.info("Database initialized")
    
    # Initialize storage
    await model_storage.initialize()
    logger.info("Model storage initialized")
    
    # Initialize registry
    await model_registry.initialize()
    logger.info("Model registry initialized")
    
    # Load active model
    active_model = await model_registry.get_active_model()
    if active_model:
        await model_manager.load_model(active_model)
        logger.info(f"Active model loaded: {active_model.version}")
    
    yield
    
    # Shutdown
    logger.info("Shutting down Model Registry Service...")
    await model_manager.unload_model()
    await model_storage.close()

app = FastAPI(
    title="Agriculture AI Model Registry",
    description="Model versioning, storage, and deployment management",
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
        "service": "model-registry",
        "active_model": model_manager.current_model_version,
        "model_loaded": model_manager.is_loaded
    }

@app.get("/ready")
async def readiness_check():
    return {
        "ready": True,
        "database": True,
        "storage": await model_storage.health_check()
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8005,
        reload=settings.DEBUG
    )