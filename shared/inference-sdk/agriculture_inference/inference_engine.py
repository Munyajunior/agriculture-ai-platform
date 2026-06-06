# shared/inference-sdk/agriculture_inference/inference_engine.py
"""Core inference engine with multiple backend support"""

import numpy as np
from typing import Union, Optional, Dict, Any, Tuple, List
from pathlib import Path
import asyncio
from concurrent.futures import ThreadPoolExecutor
import logging

logger = logging.getLogger(__name__)


class InferenceEngine:
    """Unified inference engine supporting ONNX, PyTorch, and TensorRT"""
    
    def __init__(self, backend: str = "onnx"):
        """
        Initialize inference engine
        
        Args:
            backend: "onnx", "pytorch", or "tensorrt"
        """
        self.backend = backend
        self.session = None
        self.input_name = None
        self.output_name = None
        self.is_loaded = False
        self.executor = ThreadPoolExecutor(max_workers=2)
        
    async def load_model(
        self,
        model_path: Union[str, Path],
        model_config: Optional[Dict[str, Any]] = None
    ):
        """Load model for inference"""
        
        if self.backend == "onnx":
            import onnxruntime as ort
            
            # Set providers based on availability
            providers = ['CPUExecutionProvider']
            if 'CUDAExecutionProvider' in ort.get_available_providers():
                providers.insert(0, 'CUDAExecutionProvider')
            
            self.session = ort.InferenceSession(
                str(model_path),
                providers=providers
            )
            
            # Get input/output names
            self.input_name = self.session.get_inputs()[0].name
            self.output_name = self.session.get_outputs()[0].name
            
            self.is_loaded = True
            logger.info(f"ONNX model loaded from {model_path} using {providers[0]}")
            
        elif self.backend == "pytorch":
            import torch
            
            # Load PyTorch model
            self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
            self.session = torch.jit.load(str(model_path), map_location=self.device)
            self.session.eval()
            
            self.is_loaded = True
            logger.info(f"PyTorch model loaded on {self.device}")
            
        else:
            raise ValueError(f"Unsupported backend: {self.backend}")
    
    async def predict(
        self,
        input_tensor: np.ndarray,
        return_probabilities: bool = True
    ) -> Tuple[int, np.ndarray, float]:
        """Run inference on single input"""
        
        if not self.is_loaded:
            raise RuntimeError("Model not loaded")
        
        import time
        start_time = time.time()
        
        if self.backend == "onnx":
            # ONNX Runtime inference
            input_dict = {self.input_name: input_tensor}
            outputs = self.session.run([self.output_name], input_dict)
            probabilities = outputs[0][0]
            prediction = int(np.argmax(probabilities))
            
        elif self.backend == "pytorch":
            import torch
            
            # Convert to tensor
            input_tensor = torch.from_numpy(input_tensor).float()
            input_tensor = input_tensor.to(self.device)
            
            with torch.no_grad():
                logits = self.session(input_tensor)
                probabilities = torch.softmax(logits, dim=1)
                prediction = int(torch.argmax(probabilities, dim=1).cpu().numpy()[0])
                probabilities = probabilities.cpu().numpy()[0]
        
        inference_time = (time.time() - start_time) * 1000
        
        return prediction, probabilities, inference_time
    
    async def batch_predict(
        self,
        input_batch: List[np.ndarray],
        batch_size: int = 32
    ) -> List[Tuple[int, np.ndarray, float]]:
        """Run batch inference"""
        
        results = []
        
        for i in range(0, len(input_batch), batch_size):
            batch = input_batch[i:i + batch_size]
            batch_tasks = [self.predict(img) for img in batch]
            batch_results = await asyncio.gather(*batch_tasks)
            results.extend(batch_results)
        
        return results
    
    async def predict_async(self, input_tensor: np.ndarray):
        """Async prediction — delegates to predict() directly."""
        return await self.predict(input_tensor)
    
    def unload(self):
        """Unload model and free resources"""
        self.session = None
        self.is_loaded = False
        logger.info("Model unloaded")