# services/model-registry/app/api/v1/models.py
"""Model management endpoints"""

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, status
from typing import List, Optional
from uuid import UUID
from datetime import datetime

from ...core.registry import ModelRegistry
from ...core.model_manager import ModelManager
from ...database import ModelVersion, ModelStatus
from ...schemas import (
    ModelCreate, ModelResponse, ModelUpdate,
    ModelListResponse, ModelCompareResponse
)
from ..dependencies import verify_api_key

router = APIRouter()
registry = ModelRegistry()
model_manager = ModelManager()


@router.post("/register", response_model=ModelResponse)
async def register_model(
    version: str = Form(...),
    model_type: str = Form(...),
    framework: str = Form(...),
    accuracy: Optional[float] = Form(None),
    model_file: UploadFile = File(...),
    onnx_file: Optional[UploadFile] = File(None),
    quantized_file: Optional[UploadFile] = File(None),
    api_key: str = Depends(verify_api_key)
):
    """Register a new model version"""
    
    try:
        # Read model files
        model_data = await model_file.read()
        onnx_data = await onnx_file.read() if onnx_file else None
        quantized_data = await quantized_file.read() if quantized_file else None
        
        # Prepare model metadata
        model_info = {
            "version": version,
            "model_type": model_type,
            "framework": framework,
            "accuracy": accuracy,
            "created_by": "api"
        }
        
        # Register model
        model = await registry.register_model(
            model_info,
            model_data,
            onnx_data,
            quantized_data
        )
        
        return model
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Model registration failed: {str(e)}"
        )


@router.get("/", response_model=ModelListResponse)
async def list_models(
    model_type: Optional[str] = None,
    status: Optional[ModelStatus] = None,
    limit: int = 100,
    offset: int = 0
):
    """List all models"""
    
    models = await registry.list_models(model_type, status, limit, offset)
    total = len(models)
    
    return ModelListResponse(
        total=total,
        models=models,
        limit=limit,
        offset=offset
    )


@router.get("/active", response_model=ModelResponse)
async def get_active_model():
    """Get currently active model"""
    
    model = await registry.get_active_model()
    if not model:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No active model found"
        )
    
    return model


@router.get("/{model_id}", response_model=ModelResponse)
async def get_model(model_id: UUID):
    """Get model by ID"""
    
    model = await registry.get_model(model_id)
    if not model:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Model not found"
        )
    
    return model


@router.put("/{model_id}/status")
async def update_model_status(
    model_id: UUID,
    status: ModelStatus,
    is_active: bool = False
):
    """Update model status"""
    
    try:
        model = await registry.update_model_status(model_id, status, is_active)
        
        # If activated, load the model
        if is_active:
            await model_manager.load_model(model)
        
        return {"message": "Model status updated", "model": model}
        
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.post("/{model_id}/promote")
async def promote_to_production(model_id: UUID, reason: Optional[str] = None):
    """Promote model to production"""
    
    try:
        model = await registry.promote_to_production(model_id, reason)
        return {"message": "Model promoted to production", "model": model}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.post("/compare", response_model=ModelCompareResponse)
async def compare_models(model_ids: List[UUID]):
    """Compare multiple models"""
    
    comparison = await registry.compare_models(model_ids)
    return comparison


@router.get("/{model_id}/download")
async def download_model(
    model_id: UUID,
    format: str = "pytorch"
):
    """Get download URL for model"""
    
    try:
        url = await registry.get_model_download_url(model_id, format)
        return {"download_url": url, "expires_in": 3600}
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))