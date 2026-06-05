# services/model-registry/app/core/model_manager.py
"""Model manager for loading and serving models"""

import torch
import onnxruntime as ort
import numpy as np
from typing import Optional, Dict, Any, Tuple
from pathlib import Path
import asyncio
import logging
from PIL import Image
import io

from .registry import ModelRegistry
from ..config import settings

logger = logging.getLogger(__name__)


class ModelManager:
    """Manage model loading, caching, and inference"""
    
    def __init__(self):
        self.registry = ModelRegistry()
        self.current_model: Optional[Any] = None
        self.current_model_version: Optional[str] = None
        self.is_loaded = False
        self.model_type = None
        self.use_gpu = torch.cuda.is_available()
        self.onnx_session = None
        
    async def load_model(self, model_version) -> bool:
        """Load a model version"""
        try:
            # Download model file if not cached
            cache_path = Path(settings.MODEL_CACHE_PATH) / f"{model_version.id}"
            cache_path.mkdir(parents=True, exist_ok=True)
            
            model_file = cache_path / "model.pth"
            
            if not model_file.exists():
                # Download from storage
                url = await self.registry.get_model_download_url(model_version.id, "pytorch")
                # Download logic here (use httpx)
                pass
            
            # Load based on framework
            if model_version.model_framework.value == "pytorch":
                self.current_model = self._load_pytorch_model(model_file, model_version)
            elif model_version.model_framework.value == "onnx":
                self.onnx_session = self._load_onnx_model(cache_path / "model.onnx")
            else:
                raise ValueError(f"Unsupported framework: {model_version.model_framework}")
            
            self.current_model_version = model_version.version
            self.model_type = model_version.model_type
            self.is_loaded = True
            
            logger.info(f"Loaded model version {model_version.version}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to load model: {e}")
            self.is_loaded = False
            return False
    
    def _load_pytorch_model(self, model_path: Path, model_version):
        """Load PyTorch model"""
        # Import model architecture
        from ..models.architectures import get_model_architecture
        
        model = get_model_architecture(
            model_version.model_type,
            num_classes=model_version.num_classes
        )
        
        checkpoint = torch.load(model_path, map_location='cuda' if self.use_gpu else 'cpu')
        
        if 'model_state_dict' in checkpoint:
            model.load_state_dict(checkpoint['model_state_dict'])
        else:
            model.load_state_dict(checkpoint)
        
        model.eval()
        
        if self.use_gpu:
            model = model.cuda()
        
        return model
    
    def _load_onnx_model(self, model_path: Path) -> ort.InferenceSession:
        """Load ONNX model"""
        providers = ['CUDAExecutionProvider', 'CPUExecutionProvider'] if self.use_gpu else ['CPUExecutionProvider']
        
        session = ort.InferenceSession(
            str(model_path),
            providers=providers
        )
        
        return session
    
    async def unload_model(self):
        """Unload current model"""
        self.current_model = None
        self.onnx_session = None
        self.is_loaded = False
        self.current_model_version = None
        
        if self.use_gpu:
            torch.cuda.empty_cache()
        
        logger.info("Model unloaded")
    
    async def predict(
        self,
        image: np.ndarray,
        return_probabilities: bool = True
    ) -> Tuple[int, np.ndarray, float]:
        """Run inference on image"""
        if not self.is_loaded:
            raise RuntimeError("No model loaded")
        
        import time
        start_time = time.time()
        
        # Preprocess image
        processed = self._preprocess_image(image)
        
        if self.onnx_session:
            # ONNX inference
            input_name = self.onnx_session.get_inputs()[0].name
            output_name = self.onnx_session.get_outputs()[0].name
            
            result = self.onnx_session.run([output_name], {input_name: processed})
            probabilities = result[0][0]
            prediction = np.argmax(probabilities)
        else:
            # PyTorch inference
            input_tensor = torch.from_numpy(processed).float()
            
            if self.use_gpu:
                input_tensor = input_tensor.cuda()
            
            with torch.no_grad():
                logits = self.current_model(input_tensor)
                probabilities = torch.softmax(logits, dim=1)
                prediction = torch.argmax(probabilities, dim=1)
                
                prediction = prediction.cpu().item()
                probabilities = probabilities.cpu().numpy()[0]
        
        inference_time = (time.time() - start_time) * 1000
        
        return prediction, probabilities, inference_time
    
    def _preprocess_image(self, image: np.ndarray) -> np.ndarray:
        """Preprocess image for model input"""
        from torchvision import transforms
        
        # Default preprocessing
        transform = transforms.Compose([
            transforms.ToPILImage(),
            transforms.Resize((224, 224)),
            transforms.ToTensor(),
            transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225])
        ])
        
        tensor = transform(image)
        
        if self.onnx_session:
            # ONNX expects numpy array
            return tensor.unsqueeze(0).numpy()
        else:
            # PyTorch expects tensor
            return tensor.unsqueeze(0).numpy()
    
    async def get_model_info(self) -> Dict[str, Any]:
        """Get current model information"""
        return {
            "is_loaded": self.is_loaded,
            "model_version": self.current_model_version,
            "model_type": self.model_type,
            "device": "cuda" if self.use_gpu and self.current_model else "cpu",
            "framework": "onnx" if self.onnx_session else "pytorch"
        }