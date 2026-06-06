# services/ai-service/main.py
"""AI Service - Main Entry Point"""

import logging
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.api.v1 import api_router
from app.core.model_registry import ModelRegistry
from app.core.inference_engine import InferenceEngine
from app.core.database import init_db
from app.worker import celery_app

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Global instances
model_registry = ModelRegistry()
inference_engine = InferenceEngine()

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager"""
    # Startup
    logger.info("Starting AI Service...")
    
    # Initialize database
    await init_db()
    logger.info("Database initialized")
    
    # Load default model
    await model_registry.initialize()
    active_model = await model_registry.get_active_model_info()
    model_path = Path(active_model.get("model_path", settings.MODEL_PATH))
    use_onnx = bool(active_model.get("use_onnx", settings.USE_ONNX))

    if use_onnx and not model_path.exists():
        logger.warning("ONNX model file not found at %s; service started without a loaded model", model_path)
    else:
        await inference_engine.load_model(
            model_path=model_path,
            model_type=active_model.get("model_type", settings.MODEL_TYPE),
            num_classes=active_model.get("num_classes", settings.NUM_CLASSES),
            use_onnx=use_onnx,
        )
        logger.info("AI model loaded")
    
    yield
    
    # Shutdown
    logger.info("Shutting down AI Service...")
    await inference_engine.unload_model()

app = FastAPI(
    title="Agriculture AI Inference Service",
    description="AI model serving for plant disease detection",
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

# Include routers
app.include_router(api_router, prefix="/api/v1")

@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "service": "ai-service",
        "model_loaded": inference_engine.is_loaded,
        "active_model": model_registry.active_model_version
    }

@app.get("/ready")
async def readiness_check():
    return {
        "ready": inference_engine.is_loaded,
        "database": True
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8002,
        reload=settings.DEBUG
    )
