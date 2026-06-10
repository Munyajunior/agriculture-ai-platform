"""Shared model helpers for training, export, and evaluation."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import torch
import torch.nn as nn
import torchvision.models as models


def build_mobilenetv3_classifier(
    num_classes: int,
    *,
    pretrained: bool = False,
) -> nn.Module:
    """Build the MobileNetV3 classifier architecture used by this project."""

    weights = models.MobileNet_V3_Large_Weights.DEFAULT if pretrained else None
    model = models.mobilenet_v3_large(weights=weights)
    in_features = model.classifier[0].in_features
    model.classifier = nn.Sequential(
        nn.Linear(in_features, 1024),
        nn.Hardswish(),
        nn.Dropout(0.2),
        nn.Linear(1024, num_classes),
    )
    return model


def load_checkpoint(path: Path, map_location: str | torch.device = "cpu") -> dict[str, Any]:
    return torch.load(path, map_location=map_location)


def load_checkpoint_model(
    path: Path,
    *,
    num_classes: int | None = None,
    device: str | torch.device = "cpu",
) -> tuple[nn.Module, dict[str, Any]]:
    """Load the trained PyTorch checkpoint and return model plus checkpoint metadata."""

    checkpoint = load_checkpoint(path, map_location=device)
    resolved_num_classes = int(num_classes or checkpoint.get("num_classes", 15))
    model = build_mobilenetv3_classifier(resolved_num_classes, pretrained=False)
    model.load_state_dict(checkpoint["model_state_dict"])
    model.to(device)
    model.eval()
    return model, checkpoint
