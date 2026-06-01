# services/ai-service/app/models/mobilenetv3.py
"""MobileNetV3 model implementation for plant disease detection"""

import torch
import torch.nn as nn
import torchvision.models as models
from typing import Dict, Any, Tuple
import numpy as np


class PlantDiseaseModel(nn.Module):
    """MobileNetV3-based plant disease classifier"""
    
    def __init__(
        self,
        num_classes: int = 15,
        pretrained: bool = True,
        dropout_rate: float = 0.2
    ):
        super().__init__()
        
        # Use MobileNetV3 Large as backbone
        self.backbone = models.mobilenet_v3_large(pretrained=pretrained)
        
        # Get the number of features from the classifier
        in_features = self.backbone.classifier[-1].in_features
        
        # Replace classifier for our number of classes
        self.backbone.classifier = nn.Sequential(
            nn.Linear(in_features, 1024),
            nn.Hardswish(),
            nn.Dropout(p=dropout_rate),
            nn.Linear(1024, 512),
            nn.Hardswish(),
            nn.Dropout(p=dropout_rate),
            nn.Linear(512, num_classes)
        )
        
        # Additional metrics
        self.num_classes = num_classes
        
    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """Forward pass"""
        return self.backbone(x)
    
    def predict(self, x: torch.Tensor) -> Tuple[torch.Tensor, torch.Tensor]:
        """Predict with confidence scores"""
        logits = self.forward(x)
        probabilities = torch.softmax(logits, dim=1)
        predictions = torch.argmax(probabilities, dim=1)
        return predictions, probabilities


class ModelFactory:
    """Factory for creating different model architectures"""
    
    @staticmethod
    def create_model(
        model_type: str = "mobilenetv3",
        num_classes: int = 15,
        pretrained: bool = True
    ) -> nn.Module:
        """Create model instance"""
        
        if model_type == "mobilenetv3":
            return PlantDiseaseModel(
                num_classes=num_classes,
                pretrained=pretrained
            )
        elif model_type == "resnet50":
            # Future support for ResNet50
            model = models.resnet50(pretrained=pretrained)
            in_features = model.fc.in_features
            model.fc = nn.Linear(in_features, num_classes)
            return model
        elif model_type == "efficientnet":
            # Future support for EfficientNet
            model = models.efficientnet_b0(pretrained=pretrained)
            in_features = model.classifier[-1].in_features
            model.classifier[-1] = nn.Linear(in_features, num_classes)
            return model
        else:
            raise ValueError(f"Unsupported model type: {model_type}")
    
    @staticmethod
    def get_model_config(model_type: str) -> Dict[str, Any]:
        """Get model configuration"""
        configs = {
            "mobilenetv3": {
                "input_size": (224, 224),
                "mean": [0.485, 0.456, 0.406],
                "std": [0.229, 0.224, 0.225],
                "model_size_mb": 12.5,
                "inference_time_ms": 25,  # on mobile
                "quantizable": True
            },
            "resnet50": {
                "input_size": (224, 224),
                "mean": [0.485, 0.456, 0.406],
                "std": [0.229, 0.224, 0.225],
                "model_size_mb": 98.0,
                "inference_time_ms": 50,
                "quantizable": False
            }
        }
        return configs.get(model_type, configs["mobilenetv3"])