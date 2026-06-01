# services/ai-service/app/core/inference_engine.py
"""Inference engine for model serving"""

import torch
import torch.nn as nn
import numpy as np
from typing import Optional, Dict, Any, Tuple, List
from PIL import Image
import cv2
import asyncio
from concurrent.futures import ThreadPoolExecutor
import logging
from pathlib import Path

from ..models.mobilenetv3 import ModelFactory
from ..config import settings
from ..preprocessing.image_processor import ImageProcessor

logger = logging.getLogger(__name__)


class InferenceEngine:
    """Unified inference engine supporting CPU, GPU, and ONNX runtime"""
    
    def __init__(self):
        self.model: Optional[nn.Module] = None
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.is_loaded = False
        self.executor = ThreadPoolExecutor(max_workers=4)
        self.image_processor = ImageProcessor()
        self.model_config = None
        
    async def load_model(
        self,
        model_path: Optional[Path] = None,
        model_type: str = "mobilenetv3",
        num_classes: int = 15,
        use_onnx: bool = False
    ):
        """Load AI model for inference"""
        try:
            if use_onnx:
                # Load ONNX model
                import onnxruntime as ort
                self.onnx_session = ort.InferenceSession(
                    str(model_path),
                    providers=['CPUExecutionProvider']
                )
                self.is_loaded = True
                self.model_config = ModelFactory.get_model_config(model_type)
                logger.info(f"ONNX model loaded from {model_path}")
            else:
                # Load PyTorch model
                self.model = ModelFactory.create_model(
                    model_type=model_type,
                    num_classes=num_classes,
                    pretrained=False
                )
                
                if model_path and model_path.exists():
                    checkpoint = torch.load(model_path, map_location=self.device)
                    self.model.load_state_dict(checkpoint['model_state_dict'])
                    logger.info(f"Model loaded from {model_path}")
                
                self.model = self.model.to(self.device)
                self.model.eval()
                self.is_loaded = True
                self.model_config = ModelFactory.get_model_config(model_type)
                logger.info(f"PyTorch model loaded on {self.device}")
                
        except Exception as e:
            logger.error(f"Failed to load model: {e}")
            raise
    
    async def unload_model(self):
        """Unload model from memory"""
        if self.model:
            del self.model
            self.model = None
        if hasattr(self, 'onnx_session'):
            del self.onnx_session
        self.is_loaded = False
        torch.cuda.empty_cache()
        logger.info("Model unloaded")
    
    async def predict(
        self,
        image: np.ndarray,
        return_probabilities: bool = True
    ) -> Tuple[int, np.ndarray, float]:
        """Run inference on single image"""
        if not self.is_loaded:
            raise RuntimeError("No model loaded")
        
        # Preprocess image
        processed_image = await self.image_processor.process(
            image,
            target_size=tuple(self.model_config['input_size'])
        )
        
        # Run inference
        start_time = asyncio.get_event_loop().time()
        
        if hasattr(self, 'onnx_session'):
            # ONNX inference
            input_name = self.onnx_session.get_inputs()[0].name
            output_name = self.onnx_session.get_outputs()[0].name
            
            # Convert to numpy for ONNX
            input_tensor = processed_image.numpy()
            result = self.onnx_session.run([output_name], {input_name: input_tensor})
            probabilities = result[0][0]
            prediction = np.argmax(probabilities)
        else:
            # PyTorch inference
            input_tensor = processed_image.unsqueeze(0).to(self.device)
            
            with torch.no_grad():
                logits = self.model(input_tensor)
                probabilities = torch.softmax(logits, dim=1)
                prediction = torch.argmax(probabilities, dim=1)
                
                prediction = prediction.cpu().item()
                probabilities = probabilities.cpu().numpy()[0]
        
        inference_time = (asyncio.get_event_loop().time() - start_time) * 1000
        
        return prediction, probabilities, inference_time
    
    async def batch_predict(
        self,
        images: List[np.ndarray],
        batch_size: int = 32
    ) -> List[Tuple[int, np.ndarray, float]]:
        """Run batch inference on multiple images"""
        results = []
        
        for i in range(0, len(images), batch_size):
            batch = images[i:i + batch_size]
            batch_tasks = [self.predict(img) for img in batch]
            batch_results = await asyncio.gather(*batch_tasks)
            results.extend(batch_results)
        
        return results
    
    async def extract_features(
        self,
        image: np.ndarray,
        layer_name: Optional[str] = None
    ) -> np.ndarray:
        """Extract feature embeddings from image"""
        if not self.is_loaded or hasattr(self, 'onnx_session'):
            raise NotImplementedError("Feature extraction only available for PyTorch models")
        
        processed_image = await self.image_processor.process(
            image,
            target_size=tuple(self.model_config['input_size'])
        )
        
        # Register hook to extract features
        features = None
        
        def hook_fn(module, input, output):
            nonlocal features
            features = output.detach()
        
        # Attach hook to specified layer
        if layer_name:
            target_layer = dict(self.model.named_modules())[layer_name]
            handle = target_layer.register_forward_hook(hook_fn)
        
        input_tensor = processed_image.unsqueeze(0).to(self.device)
        
        with torch.no_grad():
            _ = self.model(input_tensor)
        
        if layer_name:
            handle.remove()
        
        return features.cpu().numpy() if features is not None else None
    
    def get_model_info(self) -> Dict[str, Any]:
        """Get model information"""
        return {
            "is_loaded": self.is_loaded,
            "device": str(self.device),
            "model_config": self.model_config,
            "input_size": self.model_config['input_size'],
            "num_classes": self.model.get_num_classes() if hasattr(self.model, 'get_num_classes') else None
        }