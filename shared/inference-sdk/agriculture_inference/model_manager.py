# shared/inference-sdk/agriculture_inference/model_manager.py
"""Model version management and downloading"""

import json
import hashlib
from pathlib import Path
from typing import Dict, Any, Optional, List
import aiohttp
import asyncio
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


class ModelManager:
    """Manage model versions, downloads, and caching"""
    
    def __init__(self, cache_dir: Path = Path("./models")):
        self.cache_dir = cache_dir
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.models_metadata = {}
        self.active_model = None
        
    async def fetch_model_metadata(
        self,
        registry_url: str,
        model_version: Optional[str] = None
    ) -> Dict[str, Any]:
        """Fetch model metadata from registry"""
        
        async with aiohttp.ClientSession() as session:
            if model_version:
                url = f"{registry_url}/api/v1/models/{model_version}"
            else:
                url = f"{registry_url}/api/v1/models/latest"
            
            async with session.get(url) as response:
                if response.status == 200:
                    metadata = await response.json()
                    return metadata
                else:
                    raise Exception(f"Failed to fetch model metadata: {response.status}")
    
    async def download_model(
        self,
        download_url: str,
        model_version: str,
        model_type: str = "onnx"
    ) -> Path:
        """Download model file from URL"""
        
        model_path = self.cache_dir / f"{model_version}_{model_type}.onnx"
        
        if model_path.exists():
            logger.info(f"Model already exists at {model_path}")
            return model_path
        
        logger.info(f"Downloading model from {download_url}")
        
        async with aiohttp.ClientSession() as session:
            async with session.get(download_url) as response:
                if response.status == 200:
                    with open(model_path, 'wb') as f:
                        while True:
                            chunk = await response.content.read(8192)
                            if not chunk:
                                break
                            f.write(chunk)
                    
                    # Verify checksum
                    sha256_hash = hashlib.sha256()
                    with open(model_path, 'rb') as f:
                        for byte_block in iter(lambda: f.read(4096), b""):
                            sha256_hash.update(byte_block)
                    
                    logger.info(f"Model downloaded to {model_path}")
                    return model_path
                else:
                    raise Exception(f"Failed to download model: {response.status}")
    
    async def get_model(
        self,
        registry_url: str,
        model_version: Optional[str] = None,
        force_download: bool = False
    ) -> Path:
        """Get model file, downloading if necessary"""
        
        # Fetch metadata
        metadata = await self.fetch_model_metadata(registry_url, model_version)
        
        model_path = self.cache_dir / f"{metadata['version']}_onnx.onnx"
        
        if not force_download and model_path.exists():
            logger.info(f"Using cached model: {model_path}")
            self.active_model = metadata
            return model_path
        
        # Download model
        model_url = metadata.get('onnx_url') or metadata.get('model_url')
        if not model_url:
            raise Exception("No model URL found in metadata")
        
        model_path = await self.download_model(model_url, metadata['version'], 'onnx')
        self.active_model = metadata
        
        # Save metadata locally
        metadata_path = self.cache_dir / f"{metadata['version']}_metadata.json"
        with open(metadata_path, 'w') as f:
            json.dump(metadata, f, indent=2)
        
        return model_path
    
    def list_local_models(self) -> List[Dict[str, Any]]:
        """List all locally cached models"""
        
        models = []
        for model_file in self.cache_dir.glob("*_onnx.onnx"):
            metadata_file = model_file.with_name(
                model_file.name.replace("_onnx.onnx", "_metadata.json")
            )
            
            if metadata_file.exists():
                with open(metadata_file, 'r') as f:
                    metadata = json.load(f)
                    models.append({
                        'path': model_file,
                        'metadata': metadata,
                        'size_mb': model_file.stat().st_size / (1024 * 1024)
                    })
        
        return models
    
    def clear_cache(self, model_version: Optional[str] = None):
        """Clear model cache"""
        
        if model_version:
            model_path = self.cache_dir / f"{model_version}_onnx.onnx"
            metadata_path = self.cache_dir / f"{model_version}_metadata.json"
            
            if model_path.exists():
                model_path.unlink()
            if metadata_path.exists():
                metadata_path.unlink()
            
            logger.info(f"Cleared cache for model {model_version}")
        else:
            # Clear all models
            for file in self.cache_dir.glob("*"):
                file.unlink()
            logger.info("Cleared entire model cache")