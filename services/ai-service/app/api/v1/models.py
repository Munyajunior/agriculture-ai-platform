# services/ai-service/app/api/v1/models.py
"""Model management API endpoints"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from uuid import UUID

from ....core.model_registry import model_registry
from ....core.inference_engine import inference_engine
from ....core.database import get_db
from ....schemas.model import (
    ModelInfo,
    ModelVersion,
    ModelDownloadRequest,
    ModelActivateRequest,
    ModelMetadata
)

router = APIRouter()


@router.get("/", response_model=List[ModelInfo])
async def list_models(
    active_only: bool = Query(False, description="Show only active models"),
    db = Depends(get_db)
):
    """
    List all available models
    """
    try:
        models = await model_registry.fetch_available_models()
        
        if active_only:
            models = [m for m in models if m.get('is_active', False)]
        
        return models
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list models: {str(e)}"
        )


@router.get("/latest", response_model=ModelInfo)
async def get_latest_model(
    db = Depends(get_db)
):
    """
    Get the latest model version
    """
    try:
        models = await model_registry.fetch_available_models()
        
        if not models:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No models found"
            )
        
        # Sort by version and get latest
        latest = sorted(models, key=lambda x: x.get('version', ''), reverse=True)[0]
        
        return latest
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get latest model: {str(e)}"
        )


@router.get("/active", response_model=ModelInfo)
async def get_active_model(
    db = Depends(get_db)
):
    """
    Get the currently active model
    """
    try:
        active_model = await model_registry.get_active_model_info()
        
        if not active_model:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No active model found"
            )
        
        return active_model
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get active model: {str(e)}"
        )


@router.get("/{model_id}", response_model=ModelInfo)
async def get_model(
    model_id: str,
    db = Depends(get_db)
):
    """
    Get model by ID or version
    """
    try:
        models = await model_registry.fetch_available_models()
        
        # Find by ID or version
        model = None
        for m in models:
            if m.get('id') == model_id or m.get('version') == model_id:
                model = m
                break
        
        if not model:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Model not found: {model_id}"
            )
        
        return model
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get model: {str(e)}"
        )


@router.post("/activate", response_model=ModelInfo)
async def activate_model(
    request: ModelActivateRequest,
    db = Depends(get_db)
):
    """
    Activate a specific model version
    """
    try:
        # Check if model exists
        models = await model_registry.fetch_available_models()
        model_exists = any(m.get('version') == request.version for m in models)
        
        if not model_exists:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Model version not found: {request.version}"
            )
        
        # Set active model
        await model_registry.set_active_model(request.version)
        
        # Download and load model if requested
        if request.load_immediately:
            model_path = await model_registry.download_model(
                request.version,
                destination=f"/models/{request.version}.onnx"
            )
            await inference_engine.load_model(model_path)
        
        # Get updated model info
        active_model = await model_registry.get_active_model_info()
        
        return active_model
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to activate model: {str(e)}"
        )


@router.post("/download", response_model=dict)
async def download_model(
    request: ModelDownloadRequest,
    db = Depends(get_db)
):
    """
    Download a model version
    """
    try:
        model_path = await model_registry.download_model(
            request.version,
            destination=request.destination_path
        )
        
        return {
            "status": "success",
            "message": f"Model {request.version} downloaded",
            "path": str(model_path),
            "size_mb": model_path.stat().st_size / (1024 * 1024)
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to download model: {str(e)}"
        )


@router.post("/validate")
async def validate_model(
    model_path: str = Query(..., description="Path to model file"),
    db = Depends(get_db)
):
    """
    Validate a model file
    """
    from pathlib import Path
    
    model_file = Path(model_path)
    
    if not model_file.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Model file not found"
        )
    
    try:
        # Try to load the model
        import onnxruntime as ort
        
        # Check if it's a valid ONNX model
        session = ort.InferenceSession(str(model_file))
        
        # Get model metadata
        input_shape = session.get_inputs()[0].shape
        output_shape = session.get_outputs()[0].shape
        
        return {
            "status": "valid",
            "format": "onnx",
            "input_shape": input_shape,
            "output_shape": output_shape,
            "providers": session.get_providers(),
            "size_mb": model_file.stat().st_size / (1024 * 1024)
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid model: {str(e)}"
        )


@router.get("/metrics/{model_id}")
async def get_model_metrics(
    model_id: str,
    db = Depends(get_db)
):
    """
    Get performance metrics for a model
    """
    try:
        # This would fetch metrics from analytics service
        # For now, return mock data
        metrics = {
            "model_id": model_id,
            "accuracy": 0.942,
            "precision": 0.938,
            "recall": 0.931,
            "f1_score": 0.934,
            "inference_time_avg_ms": 45.2,
            "inference_time_p95_ms": 67.8,
            "model_size_mb": 12.5,
            "total_predictions": 15234,
            "last_updated": "2024-01-15T10:30:00Z"
        }
        
        return metrics
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get model metrics: {str(e)}"
        )


@router.delete("/cache")
async def clear_model_cache(
    model_version: Optional[str] = Query(None, description="Specific version to clear"),
    db = Depends(get_db)
):
    """
    Clear model cache
    """
    try:
        model_registry.clear_cache(model_version)
        
        return {
            "status": "success",
            "message": f"Cache cleared for {model_version if model_version else 'all models'}"
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to clear cache: {str(e)}"
        )