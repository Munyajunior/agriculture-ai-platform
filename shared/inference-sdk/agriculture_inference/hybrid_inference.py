# shared/inference-sdk/agriculture_inference/hybrid_inference.py
"""Hybrid inference combining edge and cloud predictions"""

import asyncio
from typing import Dict, Any, Optional, Tuple, List
from enum import Enum
import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


class InferenceMode(Enum):
    EDGE_ONLY = "edge_only"
    CLOUD_ONLY = "cloud_only"
    HYBRID = "hybrid"
    FALLBACK = "fallback"


class HybridInference:
    """Manage hybrid inference between edge and cloud"""
    
    def __init__(
        self,
        edge_engine,
        cloud_api_url: str,
        fallback_threshold: float = 0.7,
        offline_mode: bool = False
    ):
        self.edge_engine = edge_engine
        self.cloud_api_url = cloud_api_url
        self.fallback_threshold = fallback_threshold
        self.offline_mode = offline_mode
        self.pending_offline_predictions = []
        
    async def predict(
        self,
        image,
        mode: InferenceMode = InferenceMode.HYBRID,
        api_key: Optional[str] = None
    ) -> Dict[str, Any]:
        """Perform inference based on selected mode"""
        
        if mode == InferenceMode.EDGE_ONLY or self.offline_mode:
            return await self._edge_inference(image)
        
        elif mode == InferenceMode.CLOUD_ONLY:
            return await self._cloud_inference(image, api_key)
        
        elif mode == InferenceMode.HYBRID:
            return await self._hybrid_inference(image, api_key)
        
        elif mode == InferenceMode.FALLBACK:
            return await self._fallback_inference(image, api_key)
        
        else:
            raise ValueError(f"Unknown inference mode: {mode}")
    
    async def _edge_inference(self, image) -> Dict[str, Any]:
        """Perform edge-only inference"""
        
        try:
            prediction, probabilities, inference_time = await self.edge_engine.predict(image)
            
            return {
                "prediction": prediction,
                "probabilities": probabilities.tolist(),
                "inference_time_ms": inference_time,
                "source": "edge",
                "confidence": float(max(probabilities)),
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        except Exception as e:
            logger.error(f"Edge inference failed: {e}")
            raise
    
    async def _cloud_inference(self, image, api_key: Optional[str] = None) -> Dict[str, Any]:
        """Perform cloud inference via API"""
        
        import aiohttp
        import base64
        
        # Convert image to base64 if needed
        if hasattr(image, 'read'):
            image_data = base64.b64encode(image.read()).decode('utf-8')
        elif isinstance(image, bytes):
            image_data = base64.b64encode(image).decode('utf-8')
        else:
            # Assume it's a file path or numpy array - would need proper handling
            raise ValueError("Image format not supported for cloud inference")
        
        headers = {"Content-Type": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        
        async with aiohttp.ClientSession() as session:
            payload = {
                "image_base64": image_data,
                "use_edge_inference": False
            }
            
            async with session.post(
                f"{self.cloud_api_url}/api/v1/predict/single",
                json=payload,
                headers=headers
            ) as response:
                if response.status == 200:
                    result = await response.json()
                    result["source"] = "cloud"
                    return result
                else:
                    raise Exception(f"Cloud inference failed: {response.status}")
    
    async def _hybrid_inference(self, image, api_key: Optional[str] = None) -> Dict[str, Any]:
        """Hybrid: Try edge first, verify with cloud if confidence is low"""
        
        try:
            # First, try edge inference
            edge_result = await self._edge_inference(image)
            
            # If edge confidence is high enough, return edge result
            if edge_result["confidence"] >= self.fallback_threshold:
                edge_result["mode"] = "edge_only"
                return edge_result
            
            # Otherwise, verify with cloud if online
            if not self.offline_mode:
                try:
                    cloud_result = await self._cloud_inference(image, api_key)
                    cloud_result["mode"] = "hybrid_verified"
                    cloud_result["edge_confidence"] = edge_result["confidence"]
                    
                    # Store for analytics
                    await self._log_hybrid_prediction(edge_result, cloud_result)
                    
                    return cloud_result
                except Exception as e:
                    logger.warning(f"Cloud verification failed, using edge: {e}")
                    edge_result["mode"] = "edge_fallback"
                    edge_result["cloud_error"] = str(e)
                    return edge_result
            else:
                # Offline mode, store for later sync
                edge_result["mode"] = "edge_offline"
                await self._queue_offline_prediction(image, edge_result)
                return edge_result
                
        except Exception as e:
            # If edge fails, try cloud as fallback
            logger.error(f"Edge inference failed: {e}")
            if not self.offline_mode:
                return await self._cloud_inference(image, api_key)
            else:
                raise
    
    async def _fallback_inference(self, image, api_key: Optional[str] = None) -> Dict[str, Any]:
        """Try cloud first, fallback to edge if offline"""
        
        if not self.offline_mode:
            try:
                cloud_result = await self._cloud_inference(image, api_key)
                cloud_result["mode"] = "cloud_primary"
                return cloud_result
            except Exception as e:
                logger.warning(f"Cloud inference failed, falling back to edge: {e}")
                return await self._edge_inference(image)
        else:
            return await self._edge_inference(image)
    
    async def _queue_offline_prediction(self, image, result: Dict[str, Any]):
        """Queue offline prediction for later sync"""
        
        self.pending_offline_predictions.append({
            "image": image,
            "result": result,
            "timestamp": datetime.now(timezone.utc).isoformat()
        })
    
    async def sync_offline_predictions(self, api_key: str) -> List[Dict[str, Any]]:
        """Sync queued offline predictions to cloud"""
        
        synced = []
        
        for item in self.pending_offline_predictions:
            try:
                cloud_result = await self._cloud_inference(item["image"], api_key)
                synced.append({
                    "offline_result": item["result"],
                    "cloud_result": cloud_result,
                    "synced_at": datetime.now(timezone.utc).isoformat()
                })
            except Exception as e:
                logger.error(f"Failed to sync offline prediction: {e}")
        
        # Clear synced items — compare by result identity (timestamp + prediction)
        synced_results = {
            (s["offline_result"].get("timestamp"), s["offline_result"].get("prediction"))
            for s in synced
        }
        self.pending_offline_predictions = [
            item for item in self.pending_offline_predictions
            if (item["result"].get("timestamp"), item["result"].get("prediction")) not in synced_results
        ]
        
        return synced
    
    async def _log_hybrid_prediction(self, edge_result, cloud_result):
        """Log hybrid prediction for analytics"""
        
        # This could send to analytics service or log locally
        logger.info(f"Hybrid prediction - Edge conf: {edge_result['confidence']}, Cloud conf: {cloud_result['confidence']}")