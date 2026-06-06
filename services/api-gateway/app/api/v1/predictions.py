# services/api-gateway/app/api/v1/predictions.py
"""Prediction API endpoints"""

from typing import Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, status

from ...core.dependencies import get_current_active_user
from ...clients.ai_service import AIServiceClient
from ...clients.media_service import MediaServiceClient
from ...schemas.prediction import PredictionRequest, PredictionResponse, BatchPredictionRequest
from ...core.rate_limiter import limiter

router = APIRouter()
ai_client = AIServiceClient()
media_client = MediaServiceClient()


def _user_id(current_user) -> UUID:
    return UUID(str(current_user["id"]))


def _user_role(current_user) -> str:
    return current_user.get("role", "")

@router.post("/single", response_model=PredictionResponse)
@limiter.limit("10/minute")
async def predict_single(
    request: PredictionRequest,
    current_user = Depends(get_current_active_user),
    rate_limiter=Depends(limiter)
):
    """
    Perform single image prediction
    
    Supports both cloud and edge inference based on request parameters
    """
    try:
        # Process image
        if request.image_base64:
            image_data = request.image_base64
        elif request.image_url:
            # Download image from URL
            image_data = await media_client.download_image(request.image_url)
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No image source provided"
            )
        
        # Determine inference mode
        if request.use_edge_inference:
            # For edge inference, we'll return instructions for local processing
            return await ai_client.prepare_edge_inference(image_data, request)
        else:
            # Cloud inference
            prediction = await ai_client.cloud_inference(
                image_data=image_data,
                user_id=_user_id(current_user),
                farm_id=request.farm_id,
                device_type=request.device_type,
                location_lat=request.location_lat,
                location_lon=request.location_lon
            )
            
            return prediction
            
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Prediction failed: {str(e)}"
        )


@router.post("/batch", response_model=list[PredictionResponse])
@limiter.limit("5/minute")
async def predict_batch(
    request: BatchPredictionRequest,
    current_user = Depends(get_current_active_user),
    rate_limiter=Depends(limiter)
):
    """Perform batch predictions"""
    try:
        predictions = await ai_client.batch_inference(
            images=request.images,
            user_id=_user_id(current_user),
            farm_id=request.farm_id
        )
        return predictions
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Batch prediction failed: {str(e)}"
        )


@router.post("/upload-image")
@limiter.limit("20/minute")
async def upload_and_predict(
    file: UploadFile = File(...),
    farm_id: Optional[UUID] = Form(None),
    device_type: str = Form("mobile"),
    use_edge: bool = Form(False),
    current_user = Depends(get_current_active_user),
    rate_limiter=Depends(limiter)
):
    """Upload image file and get prediction"""
    try:
        # Validate file type
        if not file.content_type.startswith("image/"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="File must be an image"
            )
        
        # Upload to media service
        image_url = await media_client.upload_image(
            file=file,
            user_id=_user_id(current_user)
        )
        
        # Get prediction
        prediction = await ai_client.cloud_inference(
            image_url=image_url,
            user_id=_user_id(current_user),
            farm_id=farm_id,
            device_type=device_type
        )
        
        return prediction
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Upload and prediction failed: {str(e)}"
        )


@router.get("/history/{user_id}", response_model=list[PredictionResponse])
async def get_prediction_history(
    user_id: UUID,
    limit: int = 50,
    offset: int = 0,
    current_user = Depends(get_current_active_user)
):
    """Get prediction history for a user"""
    # Check authorization
    if _user_id(current_user) != user_id and _user_role(current_user) not in ["admin", "agronomist"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to view this user's history"
        )
    
    try:
        history = await ai_client.get_prediction_history(
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


@router.get("/{prediction_id}")
async def get_prediction_details(
    prediction_id: UUID,
    current_user = Depends(get_current_active_user)
):
    """Get detailed prediction information"""
    try:
        prediction = await ai_client.get_prediction_details(prediction_id)
        
        # Check authorization
        prediction_user_id = UUID(str(prediction.get("user_id")))
        if prediction_user_id != _user_id(current_user) and _user_role(current_user) not in ["admin", "agronomist"]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to view this prediction"
            )
        
        return prediction
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch prediction: {str(e)}"
        )
