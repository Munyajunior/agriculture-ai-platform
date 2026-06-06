# services/ai-service/app/api/v1/predictions.py
"""Prediction API endpoints"""

from typing import Optional, List
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, status
from pydantic import BaseModel

from ...core.database import get_db
from agriculture_ai.types.schemas import PredictionRequest, PredictionResponse
from ...services.prediction_service import PredictionService

router = APIRouter()
prediction_service = PredictionService()


class BatchPredictionRequest(BaseModel):
    """Batch prediction request."""

    images: List[str]
    user_id: Optional[UUID] = None
    farm_id: Optional[UUID] = None


@router.post("/single", response_model=PredictionResponse)
async def predict_single(
    request: PredictionRequest,
    db = Depends(get_db)
):
    """Perform single image prediction"""
    
    try:
        # Process image and get prediction
        result = await prediction_service.process_prediction(
            image_data=request.image_base64 or request.image_url,
            user_id=request.user_id,
            farm_id=request.farm_id,
            device_type=request.device_type,
            location_lat=request.location_lat,
            location_lon=request.location_lon
        )
        
        return result
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Prediction failed: {str(e)}"
        )


@router.post("/batch", response_model=List[PredictionResponse])
async def predict_batch(
    request: BatchPredictionRequest,
    db = Depends(get_db)
):
    """Perform batch predictions"""
    
    try:
        results = await prediction_service.process_batch_predictions(
            images=request.images,
            user_id=request.user_id,
            farm_id=request.farm_id
        )
        
        return results
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Batch prediction failed: {str(e)}"
        )


@router.post("/upload", response_model=PredictionResponse)
async def predict_upload(
    file: UploadFile = File(...),
    user_id: Optional[UUID] = Form(None),
    farm_id: Optional[UUID] = Form(None),
    device_type: str = Form("mobile"),
    db = Depends(get_db)
):
    """Upload image file and get prediction"""
    
    # Validate file type
    if not file.content_type.startswith("image/"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File must be an image"
        )
    
    try:
        # Read file content
        image_bytes = await file.read()
        
        # Process prediction
        result = await prediction_service.process_prediction_from_bytes(
            image_bytes=image_bytes,
            user_id=user_id,
            farm_id=farm_id,
            device_type=device_type,
            filename=file.filename
        )
        
        return result
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Prediction failed: {str(e)}"
        )


@router.get("/history/{user_id}", response_model=List[PredictionResponse])
async def get_prediction_history(
    user_id: UUID,
    limit: int = 50,
    offset: int = 0,
    db = Depends(get_db)
):
    """Get prediction history for user"""
    
    try:
        history = await prediction_service.get_user_predictions(
            user_id=user_id,
            limit=limit,
            offset=offset
        )
        return history
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch history: {str(e)}"
        )
