# services/ai-service/app/services/prediction_service.py
"""Prediction service business logic"""

from typing import Optional, List, Dict, Any
from uuid import UUID, uuid4
from datetime import datetime
import base64
import io
from PIL import Image
import numpy as np
import logging

from ..core.inference_engine import inference_engine
from ..core.database import AsyncSessionLocal
from agriculture_ai.types.models import Scan, Prediction, Disease, Treatment

logger = logging.getLogger(__name__)


class PredictionService:
    """Service for handling prediction logic"""
    
    async def process_prediction(
        self,
        image_data: str,
        user_id: Optional[UUID],
        farm_id: Optional[UUID],
        device_type: str,
        location_lat: Optional[float] = None,
        location_lon: Optional[float] = None
    ) -> Dict[str, Any]:
        """Process a single prediction"""
        
        # Decode image
        if image_data.startswith('data:image'):
            # Extract base64 part
            image_data = image_data.split(',')[1]
        
        image_bytes = base64.b64decode(image_data)
        image = Image.open(io.BytesIO(image_bytes))
        
        # Convert to numpy array
        image_np = np.array(image)
        
        # Run inference
        prediction_idx, probabilities, inference_time = await inference_engine.predict(image_np)
        
        # Get disease info
        disease = self._get_disease_by_index(prediction_idx)
        treatments = await self._get_treatments_for_disease(disease['id'])
        
        # Store in database
        async with AsyncSessionLocal() as db:
            # Create scan record
            scan = Scan(
                id=uuid4(),
                user_id=user_id,
                farm_id=farm_id,
                image_url=None,  # Would be set if uploaded to storage
                device_type=device_type,
                location_lat=location_lat,
                location_lon=location_lon,
                created_at=datetime.utcnow()
            )
            db.add(scan)
            await db.flush()
            
            # Create prediction record
            prediction = Prediction(
                id=uuid4(),
                scan_id=scan.id,
                disease_type=disease['disease_type'],
                confidence_score=float(np.max(probabilities)),
                inference_source="cloud",
                model_version_id=None,
                processing_time_ms=int(inference_time),
                status="completed",
                created_at=datetime.utcnow()
            )
            db.add(prediction)
            await db.commit()
            
            await db.refresh(prediction)
            
            return {
                "id": prediction.id,
                "scan_id": scan.id,
                "disease_type": disease['disease_type'],
                "confidence_score": prediction.confidence_score,
                "inference_source": "cloud",
                "processing_time_ms": prediction.processing_time_ms,
                "treatments": treatments,
                "image_url": None,
                "created_at": prediction.created_at
            }
    
    async def process_prediction_from_bytes(
        self,
        image_bytes: bytes,
        user_id: Optional[UUID],
        farm_id: Optional[UUID],
        device_type: str,
        filename: Optional[str] = None
    ) -> Dict[str, Any]:
        """Process prediction from raw bytes"""
        
        image = Image.open(io.BytesIO(image_bytes))
        image_np = np.array(image)
        
        # Run inference
        prediction_idx, probabilities, inference_time = await inference_engine.predict(image_np)
        
        # Get disease info
        disease = self._get_disease_by_index(prediction_idx)
        treatments = await self._get_treatments_for_disease(disease['id'])
        
        return {
            "id": uuid4(),
            "disease_type": disease['disease_type'],
            "confidence_score": float(np.max(probabilities)),
            "inference_source": "cloud",
            "processing_time_ms": int(inference_time),
            "treatments": treatments,
            "created_at": datetime.utcnow()
        }
    
    async def process_batch_predictions(
        self,
        images: List[str],
        user_id: Optional[UUID],
        farm_id: Optional[UUID]
    ) -> List[Dict[str, Any]]:
        """Process batch predictions"""
        
        results = []
        
        for image_data in images:
            result = await self.process_prediction(
                image_data=image_data,
                user_id=user_id,
                farm_id=farm_id,
                device_type="batch"
            )
            results.append(result)
        
        return results
    
    async def get_user_predictions(
        self,
        user_id: UUID,
        limit: int = 50,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """Get prediction history for user"""
        
        async with AsyncSessionLocal() as db:
            from sqlalchemy import select
            from sqlalchemy.orm import selectinload
            
            stmt = select(Prediction).join(Scan).where(
                Scan.user_id == user_id
            ).order_by(
                Prediction.created_at.desc()
            ).limit(limit).offset(offset)
            
            result = await db.execute(stmt)
            predictions = result.scalars().all()
            
            return [
                {
                    "id": p.id,
                    "scan_id": p.scan_id,
                    "disease_type": p.disease_type,
                    "confidence_score": p.confidence_score,
                    "inference_source": p.inference_source,
                    "processing_time_ms": p.processing_time_ms,
                    "created_at": p.created_at
                }
                for p in predictions
            ]
    
    def _get_disease_by_index(self, index: int) -> Dict[str, Any]:
        """Map model output index to disease"""
        
        # This mapping should be loaded from model metadata
        diseases_map = {
            0: {"id": 1, "disease_type": "tomato_early_blight", "name": "Tomato Early Blight"},
            1: {"id": 2, "disease_type": "tomato_late_blight", "name": "Tomato Late Blight"},
            2: {"id": 3, "disease_type": "tomato_leaf_mold", "name": "Tomato Leaf Mold"},
            3: {"id": 4, "disease_type": "cassava_mosaic", "name": "Cassava Mosaic Disease"},
            4: {"id": 5, "disease_type": "maize_rust", "name": "Maize Rust"},
            # Add more mappings as needed
        }
        
        return diseases_map.get(index, {
            "id": 0,
            "disease_type": "unknown",
            "name": "Unknown Disease"
        })
    
    async def _get_treatments_for_disease(self, disease_id: int) -> List[Dict[str, Any]]:
        """Get treatment recommendations for disease"""
        
        # This should query the database
        # For now, return mock treatments
        return [
            {
                "treatment_type": "chemical",
                "product_name": "Copper Fungicide",
                "application_method": "Spray on affected areas",
                "dosage_instructions": "Apply 2ml per liter of water",
                "frequency_days": 7,
                "organic_option": False
            },
            {
                "treatment_type": "organic",
                "product_name": "Neem Oil",
                "application_method": "Spray on leaves",
                "dosage_instructions": "Mix 5ml per liter of water",
                "frequency_days": 5,
                "organic_option": True
            }
        ]
