# shared/inference-sdk/agriculture_inference/postprocessing.py
"""Postprocessing utilities for inference results"""

import json
from collections import Counter
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Tuple
import numpy as np


class ResultProcessor:
    """Process and enhance inference results"""
    
    def __init__(self, disease_mapping: Optional[Dict[int, Dict[str, Any]]] = None):
        """
        Initialize result processor
        
        Args:
            disease_mapping: Mapping from class indices to disease information
        """
        self.disease_mapping = disease_mapping or self._get_default_mapping()
        
    def process_prediction(
        self,
        prediction_idx: int,
        probabilities: np.ndarray,
        inference_time_ms: float,
        source: str = "edge",
        confidence_threshold: float = 0.5
    ) -> Dict[str, Any]:
        """
        Process raw prediction into structured result
        
        Args:
            prediction_idx: Predicted class index
            probabilities: Array of class probabilities
            inference_time_ms: Inference time in milliseconds
            source: Inference source (edge/cloud)
            confidence_threshold: Minimum confidence to consider valid
            
        Returns:
            Structured prediction result
        """
        
        confidence = float(probabilities[prediction_idx])
        
        # Get disease information
        disease_info = self.disease_mapping.get(prediction_idx, {})
        
        # Calculate confidence level
        confidence_level = self._get_confidence_level(confidence)
        
        # Get top-k predictions
        top_k = self._get_top_k_predictions(probabilities, k=3)
        
        result = {
            "prediction": {
                "class_index": prediction_idx,
                "class_name": disease_info.get("name", "Unknown"),
                "disease_type": disease_info.get("disease_type", "unknown"),
                "confidence": confidence,
                "confidence_level": confidence_level,
                "is_reliable": confidence >= confidence_threshold
            },
            "probabilities": {
                "top_1": {
                    "class": disease_info.get("name", "Unknown"),
                    "probability": confidence
                },
                "top_k": top_k
            },
            "metadata": {
                "inference_source": source,
                "inference_time_ms": inference_time_ms,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "model_version": disease_info.get("model_version", "unknown")
            },
            "recommendations": self._generate_recommendations(
                disease_info,
                confidence,
                confidence_level
            )
        }
        
        # Add treatment information if available
        if "treatments" in disease_info:
            result["treatments"] = self._format_treatments(disease_info["treatments"])
        
        return result
    
    def process_batch_results(
        self,
        predictions: List[Tuple[int, np.ndarray, float]],
        source: str = "edge"
    ) -> List[Dict[str, Any]]:
        """Process batch of predictions"""
        
        results = []
        for pred_idx, probs, inf_time in predictions:
            result = self.process_prediction(pred_idx, probs, inf_time, source)
            results.append(result)
        
        return results
    
    def aggregate_predictions(
        self,
        predictions: List[Dict[str, Any]],
        method: str = "majority_vote"
    ) -> Dict[str, Any]:
        """
        Aggregate multiple predictions for the same image
        
        Args:
            predictions: List of prediction results
            method: Aggregation method (majority_vote, weighted_average, max_confidence)
            
        Returns:
            Aggregated prediction
        """
        
        if not predictions:
            return {}
        
        if method == "majority_vote":
            return self._majority_vote_aggregation(predictions)
        elif method == "weighted_average":
            return self._weighted_average_aggregation(predictions)
        elif method == "max_confidence":
            return self._max_confidence_aggregation(predictions)
        else:
            raise ValueError(f"Unknown aggregation method: {method}")
    
    def calculate_uncertainty(self, probabilities: np.ndarray) -> Dict[str, float]:
        """
        Calculate prediction uncertainty metrics
        
        Args:
            probabilities: Array of class probabilities
            
        Returns:
            Uncertainty metrics
        """
        
        # Sort probabilities in descending order
        sorted_probs = np.sort(probabilities)[::-1]
        
        # Calculate metrics
        max_prob = sorted_probs[0]
        second_max_prob = sorted_probs[1] if len(sorted_probs) > 1 else 0
        
        # Margin between top two predictions
        margin = max_prob - second_max_prob
        
        # Entropy (higher = more uncertain)
        entropy = -np.sum(probabilities * np.log(probabilities + 1e-8))
        max_entropy = np.log(len(probabilities))
        normalized_entropy = entropy / max_entropy
        
        # Confidence score
        confidence_score = max_prob
        
        return {
            "max_probability": float(max_prob),
            "second_max_probability": float(second_max_prob),
            "margin": float(margin),
            "entropy": float(entropy),
            "normalized_entropy": float(normalized_entropy),
            "confidence_score": float(confidence_score),
            "uncertainty_level": self._get_uncertainty_level(normalized_entropy)
        }
    
    def _get_confidence_level(self, confidence: float) -> str:
        """Convert confidence score to level"""
        
        if confidence >= 0.9:
            return "very_high"
        elif confidence >= 0.75:
            return "high"
        elif confidence >= 0.6:
            return "medium"
        elif confidence >= 0.45:
            return "low"
        else:
            return "very_low"
    
    def _get_uncertainty_level(self, normalized_entropy: float) -> str:
        """Convert normalized entropy to uncertainty level"""
        
        if normalized_entropy < 0.2:
            return "very_low"
        elif normalized_entropy < 0.4:
            return "low"
        elif normalized_entropy < 0.6:
            return "medium"
        elif normalized_entropy < 0.8:
            return "high"
        else:
            return "very_high"
    
    def _get_top_k_predictions(self, probabilities: np.ndarray, k: int = 3) -> List[Dict[str, Any]]:
        """Get top-k predictions with class names"""
        
        # Get top k indices
        top_k_indices = np.argsort(probabilities)[-k:][::-1]
        
        top_k = []
        for idx in top_k_indices:
            disease_info = self.disease_mapping.get(int(idx), {})
            top_k.append({
                "class_index": int(idx),
                "class_name": disease_info.get("name", "Unknown"),
                "disease_type": disease_info.get("disease_type", "unknown"),
                "probability": float(probabilities[idx])
            })
        
        return top_k
    
    def _generate_recommendations(
        self,
        disease_info: Dict[str, Any],
        confidence: float,
        confidence_level: str
    ) -> List[Dict[str, Any]]:
        """Generate recommendations based on prediction"""
        
        recommendations = []
        
        # Add confidence-based recommendation
        if confidence_level in ["low", "very_low"]:
            recommendations.append({
                "type": "recapture",
                "message": "Low confidence prediction. Please capture a clearer image of the affected area.",
                "priority": "high"
            })
        
        # Add disease-specific recommendations
        if disease_info.get("disease_type") != "unknown":
            recommendations.append({
                "type": "action",
                "message": f"Based on detected {disease_info.get('name', 'disease')}, immediate action is recommended.",
                "priority": "high"
            })
            
            recommendations.append({
                "type": "monitoring",
                "message": "Monitor surrounding plants for similar symptoms over the next 3-5 days.",
                "priority": "medium"
            })
        
        # Add general recommendation
        recommendations.append({
            "type": "expert",
            "message": "Consult with a local agronomist for field-specific advice.",
            "priority": "low"
        })
        
        return recommendations
    
    def _format_treatments(self, treatments: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Format treatment information for response"""
        
        formatted = []
        for treatment in treatments:
            formatted.append({
                "type": treatment.get("treatment_type", "unknown"),
                "product": treatment.get("product_name", "Not specified"),
                "application": treatment.get("application_method", "Follow label instructions"),
                "dosage": treatment.get("dosage_instructions", "As per manufacturer"),
                "frequency_days": treatment.get("frequency_days", 7),
                "organic": treatment.get("organic_option", False),
                "precautions": treatment.get("precautions", [])
            })
        
        return formatted
    
    def _majority_vote_aggregation(self, predictions: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Aggregate predictions by majority vote"""
        
        # Count class predictions
        class_votes = Counter()
        confidence_sum = 0
        
        for pred in predictions:
            class_name = pred.get("prediction", {}).get("class_name", "Unknown")
            class_votes[class_name] += 1
            confidence_sum += pred.get("prediction", {}).get("confidence", 0)
        
        # Get majority class
        majority_class = class_votes.most_common(1)[0][0]
        vote_count = class_votes[majority_class]
        
        # Calculate average confidence for majority class
        avg_confidence = confidence_sum / len(predictions)
        
        return {
            "class_name": majority_class,
            "vote_count": vote_count,
            "total_predictions": len(predictions),
            "agreement_ratio": vote_count / len(predictions),
            "average_confidence": avg_confidence
        }
    
    def _weighted_average_aggregation(self, predictions: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Aggregate predictions by confidence-weighted average"""
        
        class_scores = {}
        
        for pred in predictions:
            class_name = pred.get("prediction", {}).get("class_name", "Unknown")
            confidence = pred.get("prediction", {}).get("confidence", 0)
            
            if class_name not in class_scores:
                class_scores[class_name] = {"score": 0, "count": 0}
            
            class_scores[class_name]["score"] += confidence
            class_scores[class_name]["count"] += 1
        
        # Calculate weighted scores
        for class_name in class_scores:
            class_scores[class_name]["weighted_score"] = (
                class_scores[class_name]["score"] / class_scores[class_name]["count"]
            )
        
        # Get class with highest weighted score
        best_class = max(class_scores.items(), key=lambda x: x[1]["weighted_score"])
        
        return {
            "class_name": best_class[0],
            "weighted_confidence": best_class[1]["weighted_score"],
            "all_scores": class_scores
        }
    
    def _max_confidence_aggregation(self, predictions: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Take prediction with highest confidence"""
        
        best_prediction = max(
            predictions,
            key=lambda x: x.get("prediction", {}).get("confidence", 0)
        )
        
        return best_prediction.get("prediction", {})
    
    def _get_default_mapping(self) -> Dict[int, Dict[str, Any]]:
        """Get default disease mapping"""
        
        return {
            0: {
                "name": "Tomato Early Blight",
                "disease_type": "tomato_early_blight",
                "crop": "tomato",
                "severity": "moderate",
                "treatments": [
                    {
                        "treatment_type": "chemical",
                        "product_name": "Chlorothalonil",
                        "application_method": "Foliar spray",
                        "dosage_instructions": "Apply 1.5 ml per liter of water",
                        "frequency_days": 7,
                        "organic_option": False
                    }
                ]
            },
            1: {
                "name": "Tomato Late Blight",
                "disease_type": "tomato_late_blight",
                "crop": "tomato",
                "severity": "severe",
                "treatments": [
                    {
                        "treatment_type": "chemical",
                        "product_name": "Copper fungicide",
                        "application_method": "Spray on leaves",
                        "dosage_instructions": "Apply 2 ml per liter of water",
                        "frequency_days": 5,
                        "organic_option": True
                    }
                ]
            },
            2: {
                "name": "Cassava Mosaic Disease",
                "disease_type": "cassava_mosaic",
                "crop": "cassava",
                "severity": "severe",
                "treatments": [
                    {
                        "treatment_type": "cultural",
                        "product_name": "Resistant varieties",
                        "application_method": "Plant certified disease-free cuttings",
                        "dosage_instructions": "Use resistant varieties",
                        "frequency_days": 0,
                        "organic_option": True
                    }
                ]
            },
            3: {
                "name": "Maize Rust",
                "disease_type": "maize_rust",
                "crop": "maize",
                "severity": "moderate",
                "treatments": [
                    {
                        "treatment_type": "chemical",
                        "product_name": "Azoxystrobin",
                        "application_method": "Foliar application",
                        "dosage_instructions": "Apply 1 ml per liter of water",
                        "frequency_days": 10,
                        "organic_option": False
                    }
                ]
            }
        }