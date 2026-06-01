# services/ai-service/app/core/model_registry.py
"""Model registry for managing AI model versions"""

from typing import Dict, Any, Optional
from pathlib import Path
import json
import aiohttp
import asyncio
import logging
from datetime import datetime

from ..config import settings

logger = logging.getLogger(__name__)


class ModelRegistry:
    """Registry for managing multiple model versions"""
    
    def __init__(self):
        self.registry_url = settings.MODEL_REGISTRY_URL
        self.models: Dict[str, Dict[str, Any]] = {}
        self.active_model_version: Optional[str] = None
        
    async def initialize(self):
        """Initialize registry and load model metadata"""
        await self.fetch_available_models()
        await self.set_active_model()
        
    async def fetch_available_models(self):
        """Fetch all available models from registry"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{self.registry_url}/api/v1/models") as response:
                    if response.status == 200:
                        models_data = await response.json()
                        self.models = {model['version']: model for model in models_data}
                        logger.info(f"Fetched {len(self.models)} models from registry")
                    else:
                        logger.warning(f"Failed to fetch models: {response.status}")
        except Exception as e:
            logger.error(f"Error fetching models: {e}")
    
    async def set_active_model(self, version: Optional[str] = None):
        """Set active model version"""
        
        if version and version in self.models:
            self.active_model_version = version
        elif self.models:
            # Get latest version
            versions = sorted(self.models.keys(), reverse=True)
            self.active_model_version = versions[0]
        else:
            # Use default model path
            self.active_model_version = "default"
            self.models["default"] = {
                "version": "default",
                "model_path": settings.MODEL_PATH,
                "model_type": settings.MODEL_TYPE,
                "num_classes": settings.NUM_CLASSES,
                "accuracy": 0.0
            }
        
        logger.info(f"Active model set to: {self.active_model_version}")
    
    async def get_active_model_info(self) -> Dict[str, Any]:
        """Get information about the active model"""
        
        if self.active_model_version and self.active_model_version in self.models:
            return self.models[self.active_model_version]
        else:
            return {
                "version": "default",
                "model_path": settings.MODEL_PATH,
                "model_type": settings.MODEL_TYPE,
                "num_classes": settings.NUM_CLASSES
            }
    
    async def download_model(self, version: str, destination: Path) -> bool:
        """Download specific model version"""
        
        if version not in self.models:
            logger.error(f"Model version {version} not found in registry")
            return False
        
        model_info = self.models[version]
        download_url = model_info.get('download_url')
        
        if not download_url:
            logger.error(f"No download URL for model {version}")
            return False
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(download_url) as response:
                    if response.status == 200:
                        destination.parent.mkdir(parents=True, exist_ok=True)
                        with open(destination, 'wb') as f:
                            while True:
                                chunk = await response.content.read(8192)
                                if not chunk:
                                    break
                                f.write(chunk)
                        logger.info(f"Model {version} downloaded to {destination}")
                        return True
                    else:
                        logger.error(f"Download failed: {response.status}")
                        return False
        except Exception as e:
            logger.error(f"Error downloading model: {e}")
            return False
    
    async def check_for_updates(self):
        """Check for new model versions"""
        
        old_models = self.models.copy()
        await self.fetch_available_models()
        
        if len(self.models) > len(old_models):
            logger.info("New models available!")
            # Could trigger download of new models
            return True
        
        return False