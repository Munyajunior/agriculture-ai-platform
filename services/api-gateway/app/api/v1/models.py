# services/api-gateway/app/api/v1/models.py
"""Model management API endpoints"""

from fastapi import APIRouter, Depends, HTTPException, Query
from typing import List, Optional

from ...clients.model_registry import ModelRegistryClient
from ...core.dependencies import get_current_admin_user, get_current_active_user

router = APIRouter()
model_client = ModelRegistryClient()


@router.get("/active")
async def get_active_model(
    current_user = Depends(get_current_active_user)
):
    """Get currently active model information"""
    try:
        model = await model_client.get_active_model()
        return model
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get active model: {str(e)}"
        )


@router.get("/")
async def list_models(
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user = Depends(get_current_active_user)
):
    """List all available models"""
    try:
        models = await model_client.list_models(limit=limit, offset=offset)
        return {
            "models": models,
            "total": len(models),
            "limit": limit,
            "offset": offset
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to list models: {str(e)}"
        )


@router.get("/{model_id}")
async def get_model_details(
    model_id: str,
    current_user = Depends(get_current_active_user)
):
    """Get model details"""
    try:
        model = await model_client.get_model_by_version(model_id)
        
        if not model:
            raise HTTPException(status_code=404, detail="Model not found")
        
        return model
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get model details: {str(e)}"
        )


@router.post("/register")
async def register_model(
    model_data: dict,
    current_user = Depends(get_current_admin_user)
):
    """Register new model (admin only)"""
    try:
        model = await model_client.register_model(
            name=model_data["name"],
            version=model_data["version"],
            model_url=model_data["model_url"],
            metadata=model_data.get("metadata")
        )
        
        return model
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to register model: {str(e)}"
        )


@router.put("/{model_id}/activate")
async def activate_model(
    model_id: str,
    current_user = Depends(get_current_admin_user)
):
    """Set active model (admin only)"""
    try:
        result = await model_client.set_active_model(model_id)
        return result
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to activate model: {str(e)}"
        )


@router.get("/{model_id}/download")
async def download_model(
    model_id: str,
    format: str = Query("onnx", regex="^(onnx|pytorch|quantized)$"),
    current_user = Depends(get_current_active_user)
):
    """Get model download URL"""
    try:
        download_url = await model_client.get_model_download_url(model_id, format)
        
        return {
            "model_id": model_id,
            "format": format,
            "download_url": download_url
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get download URL: {str(e)}"
        )


@router.get("/{model_id}/metrics")
async def get_model_metrics(
    model_id: str,
    current_user = Depends(get_current_admin_user)
):
    """Get model performance metrics (admin only)"""
    try:
        metrics = await model_client.get_model_metrics(model_id)
        return metrics
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get model metrics: {str(e)}"
        )