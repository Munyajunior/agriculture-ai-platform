# services/model-registry/app/models/architectures.py
"""Model architecture definitions"""

import torch
import torch.nn as nn
import torchvision.models as models
from typing import Dict, Any


def get_model_architecture(
    model_type: str,
    num_classes: int = 15,
    pretrained: bool = True
) -> nn.Module:
    """Get model architecture by type"""
    
    if model_type == "mobilenetv3":
        return create_mobilenetv3(num_classes, pretrained)
    elif model_type == "resnet50":
        return create_resnet50(num_classes, pretrained)
    elif model_type == "efficientnet":
        return create_efficientnet(num_classes, pretrained)
    elif model_type == "yolov8":
        return create_yolov8(num_classes)
    else:
        raise ValueError(f"Unknown model type: {model_type}")


def create_mobilenetv3(num_classes: int, pretrained: bool) -> nn.Module:
    """Create MobileNetV3 model"""
    
    model = models.mobilenet_v3_large(pretrained=pretrained)
    
    # Replace classifier
    in_features = model.classifier[-1].in_features
    model.classifier[-1] = nn.Linear(in_features, num_classes)
    
    return model


def create_resnet50(num_classes: int, pretrained: bool) -> nn.Module:
    """Create ResNet50 model"""
    
    model = models.resnet50(pretrained=pretrained)
    
    # Replace final layer
    in_features = model.fc.in_features
    model.fc = nn.Linear(in_features, num_classes)
    
    return model


def create_efficientnet(num_classes: int, pretrained: bool) -> nn.Module:
    """Create EfficientNet model"""
    
    model = models.efficientnet_b0(pretrained=pretrained)
    
    # Replace classifier
    in_features = model.classifier[-1].in_features
    model.classifier[-1] = nn.Linear(in_features, num_classes)
    
    return model


def create_yolov8(num_classes: int) -> nn.Module:
    """Create YOLOv8 model (placeholder for future implementation)"""
    
    # YOLOv8 implementation would go here
    # For now, return a simple CNN
    return SimpleCNN(num_classes)


class SimpleCNN(nn.Module):
    """Simple CNN for demonstration"""
    
    def __init__(self, num_classes: int):
        super().__init__()
        
        self.features = nn.Sequential(
            nn.Conv2d(3, 32, kernel_size=3, padding=1),
            nn.ReLU(),
            nn.MaxPool2d(2),
            nn.Conv2d(32, 64, kernel_size=3, padding=1),
            nn.ReLU(),
            nn.MaxPool2d(2),
            nn.Conv2d(64, 128, kernel_size=3, padding=1),
            nn.ReLU(),
            nn.AdaptiveAvgPool2d(1)
        )
        
        self.classifier = nn.Sequential(
            nn.Flatten(),
            nn.Linear(128, 256),
            nn.ReLU(),
            nn.Dropout(0.2),
            nn.Linear(256, num_classes)
        )
    
    def forward(self, x: torch.Tensor) -> torch.Tensor:
        x = self.features(x)
        x = self.classifier(x)
        return x