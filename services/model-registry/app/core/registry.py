# services/model-registry/app/core/registry.py
"""Model registry core functionality"""

import asyncio
import json
import logging
from typing import Optional, List, Dict, Any
from datetime import datetime
from uuid import UUID, uuid4
from sqlalchemy import select, and_, desc
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import AsyncSessionLocal, ModelVersion, ModelDeployment, ModelStatus, ModelFramework
from ..config import settings
from .storage import ModelStorage

logger = logging.getLogger(__name__)


class ModelRegistry:
    """Central model registry for version management"""
    
    def __init__(self):
        self.storage = ModelStorage()
        self.cache = {}
        
    async def initialize(self):
        """Initialize registry"""
        await self.storage.initialize()
        await self._load_cache()
        logger.info("Model registry initialized")
    
    async def _load_cache(self):
        """Load active model into cache"""
        async with AsyncSessionLocal() as session:
            # Load active model
            result = await session.execute(
                select(ModelVersion).where(ModelVersion.is_active == True)
            )
            active_model = result.scalar_one_or_none()
            if active_model:
                self.cache['active_model'] = active_model.id
            
            # Load production models
            result = await session.execute(
                select(ModelVersion).where(ModelVersion.status == ModelStatus.PRODUCTION)
            )
            production_models = result.scalars().all()
            self.cache['production_models'] = [m.id for m in production_models]
    
    async def register_model(
        self,
        model_data: Dict[str, Any],
        model_file: bytes,
        onnx_file: Optional[bytes] = None,
        quantized_file: Optional[bytes] = None
    ) -> ModelVersion:
        """Register a new model version"""
        
        async with AsyncSessionLocal() as session:
            # Create model version record
            model_version = ModelVersion(
                version=model_data['version'],
                model_type=model_data['model_type'],
                model_framework=ModelFramework(model_data['framework']),
                num_classes=model_data.get('num_classes', settings.DEFAULT_NUM_CLASSES),
                classes=model_data.get('classes', []),
                input_shape=model_data.get('input_shape', [224, 224, 3]),
                output_shape=model_data.get('output_shape', [15]),
                training_dataset=model_data.get('training_dataset'),
                training_epochs=model_data.get('epochs'),
                training_batch_size=model_data.get('batch_size'),
                training_config=model_data.get('config', {}),
                accuracy=model_data.get('accuracy'),
                precision=model_data.get('precision'),
                recall=model_data.get('recall'),
                f1_score=model_data.get('f1_score'),
                metadata=model_data.get('metadata', {}),
                created_by=model_data.get('created_by', 'system'),
                status=ModelStatus.DRAFT
            )
            
            session.add(model_version)
            await session.flush()
            
            # Upload model files
            model_path = f"models/{model_version.id}/model.pth"
            await self.storage.upload_file(model_file, model_path)
            model_version.model_path = model_path
            model_version.model_size_mb = len(model_file) / (1024 * 1024)
            
            if onnx_file:
                onnx_path = f"models/{model_version.id}/model.onnx"
                await self.storage.upload_file(onnx_file, onnx_path)
                model_version.onnx_path = onnx_path
            
            if quantized_file:
                quantized_path = f"models/{model_version.id}/model_quantized.onnx"
                await self.storage.upload_file(quantized_file, quantized_path)
                model_version.quantized_path = quantized_path
            
            await session.commit()
            await session.refresh(model_version)
            
            logger.info(f"Registered model version {model_version.version} (ID: {model_version.id})")
            return model_version
    
    async def get_model(self, model_id: UUID) -> Optional[ModelVersion]:
        """Get model by ID"""
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(ModelVersion).where(ModelVersion.id == model_id)
            )
            return result.scalar_one_or_none()
    
    async def get_model_by_version(self, version: str) -> Optional[ModelVersion]:
        """Get model by version string"""
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(ModelVersion).where(ModelVersion.version == version)
            )
            return result.scalar_one_or_none()
    
    async def get_active_model(self) -> Optional[ModelVersion]:
        """Get currently active model"""
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(ModelVersion).where(ModelVersion.is_active == True)
            )
            return result.scalar_one_or_none()
    
    async def list_models(
        self,
        model_type: Optional[str] = None,
        status: Optional[ModelStatus] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[ModelVersion]:
        """List models with filters"""
        async with AsyncSessionLocal() as session:
            query = select(ModelVersion)
            
            if model_type:
                query = query.where(ModelVersion.model_type == model_type)
            if status:
                query = query.where(ModelVersion.status == status)
            
            query = query.order_by(desc(ModelVersion.created_at)).limit(limit).offset(offset)
            
            result = await session.execute(query)
            return result.scalars().all()
    
    async def update_model_status(
        self,
        model_id: UUID,
        status: ModelStatus,
        is_active: bool = False
    ) -> ModelVersion:
        """Update model status"""
        async with AsyncSessionLocal() as session:
            model = await self.get_model(model_id)
            if not model:
                raise ValueError(f"Model {model_id} not found")
            
            model.status = status
            
            if is_active:
                # Deactivate current active model
                await session.execute(
                    select(ModelVersion).where(ModelVersion.is_active == True)
                )
                current_active = await session.execute(
                    select(ModelVersion).where(ModelVersion.is_active == True)
                )
                current = current_active.scalar_one_or_none()
                if current:
                    current.is_active = False
                
                model.is_active = True
                self.cache['active_model'] = model.id
            
            if status == ModelStatus.PRODUCTION:
                model.is_deployed = True
                model.deployed_at = datetime.utcnow()
            
            model.updated_at = datetime.utcnow()
            await session.commit()
            await session.refresh(model)
            
            logger.info(f"Updated model {model.version} status to {status}")
            return model
    
    async def promote_to_production(self, model_id: UUID, reason: str = None) -> ModelVersion:
        """Promote a model to production"""
        return await self.update_model_status(model_id, ModelStatus.PRODUCTION, is_active=True)
    
    async def archive_model(self, model_id: UUID) -> ModelVersion:
        """Archive a model"""
        return await self.update_model_status(model_id, ModelStatus.ARCHIVED, is_active=False)
    
    async def record_deployment(
        self,
        model_id: UUID,
        environment: str,
        deployed_by: str,
        metadata: Dict[str, Any] = None
    ) -> ModelDeployment:
        """Record a model deployment"""
        async with AsyncSessionLocal() as session:
            deployment = ModelDeployment(
                model_id=model_id,
                environment=environment,
                deployed_by=deployed_by,
                metadata=metadata or {},
                status="success"
            )
            
            session.add(deployment)
            await session.commit()
            await session.refresh(deployment)
            
            logger.info(f"Recorded deployment of model {model_id} to {environment}")
            return deployment
    
    async def compare_models(self, model_ids: List[UUID]) -> Dict[str, Any]:
        """Compare multiple models"""
        models = []
        async with AsyncSessionLocal() as session:
            for model_id in model_ids:
                result = await session.execute(
                    select(ModelVersion).where(ModelVersion.id == model_id)
                )
                model = result.scalar_one_or_none()
                if model:
                    models.append(model)
        
        if not models:
            return {}
        
        comparison = {
            "models": [
                {
                    "id": str(m.id),
                    "version": m.version,
                    "model_type": m.model_type,
                    "accuracy": m.accuracy,
                    "precision": m.precision,
                    "recall": m.recall,
                    "f1_score": m.f1_score,
                    "model_size_mb": m.model_size_mb,
                    "inference_time_ms": m.inference_time_ms
                }
                for m in models
            ],
            "best_accuracy": max(models, key=lambda x: x.accuracy or 0).version if models else None,
            "best_f1": max(models, key=lambda x: x.f1_score or 0).version if models else None,
            "smallest_size": min(models, key=lambda x: x.model_size_mb or float('inf')).version if models else None
        }
        
        return comparison
    
    async def get_model_download_url(self, model_id: UUID, format: str = "pytorch") -> str:
        """Get presigned URL for model download"""
        model = await self.get_model(model_id)
        if not model:
            raise ValueError(f"Model {model_id} not found")
        
        if format == "pytorch":
            path = model.model_path
        elif format == "onnx":
            path = model.onnx_path
        elif format == "quantized":
            path = model.quantized_path
        else:
            raise ValueError(f"Unsupported format: {format}")
        
        if not path:
            raise ValueError(f"Model format {format} not available")
        
        return await self.storage.get_presigned_url(path)