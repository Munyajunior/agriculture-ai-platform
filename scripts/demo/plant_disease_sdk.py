#!/usr/bin/env python3
"""Small local SDK for plant disease demo inference and recommendations."""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import cv2
import numpy as np
import onnxruntime as ort


IMAGENET_MEAN = np.array([0.485, 0.456, 0.406], dtype=np.float32)
IMAGENET_STD = np.array([0.229, 0.224, 0.225], dtype=np.float32)


@dataclass(frozen=True)
class PredictionResult:
    label: str
    crop: str
    condition: str
    confidence: float
    inference_time_ms: float
    top_predictions: list[dict[str, float | str]]
    recommendations: dict[str, list[str]]


def softmax(logits: np.ndarray) -> np.ndarray:
    logits = logits.astype(np.float64)
    logits = logits - np.max(logits)
    exp = np.exp(logits)
    return (exp / exp.sum()).astype(np.float32)


def humanize(value: str) -> str:
    return value.replace("_", " ").strip().title()


def split_label(label: str) -> tuple[str, str]:
    parts = label.split("_")
    if not parts:
        return "unknown", "unknown"

    crop = parts[0]
    condition = "_".join(parts[1:]) if len(parts) > 1 else "unknown"

    if crop == "pepper" and len(parts) >= 2 and parts[1] == "bell":
        crop = "pepper_bell"
        condition = "_".join(parts[2:]) or "unknown"
    elif crop == "corn":
        crop = "corn"
    elif crop == "orange":
        crop = "orange"
    elif crop == "background":
        crop = "background"
        condition = "without_leaves"

    return crop, condition


class RecommendationEngine:
    """Rule-based agronomy recommendations for demo use."""

    DISEASE_RULES: list[tuple[tuple[str, ...], dict[str, list[str]]]] = [
        (
            ("healthy",),
            {
                "summary": ["The leaf appears healthy from the model prediction."],
                "treatment": ["No disease treatment is recommended from this image alone."],
                "control": ["Keep monitoring weekly and maintain balanced watering and nutrition."],
                "prevention": ["Avoid leaf wetness overnight and remove nearby diseased plant debris."],
            },
        ),
        (
            ("bacterial", "spot", "blight"),
            {
                "summary": ["Likely bacterial disease symptoms were detected."],
                "treatment": [
                    "Remove heavily infected leaves or plants where practical.",
                    "Use copper-based bactericide only where locally recommended and label-approved.",
                ],
                "control": [
                    "Avoid overhead irrigation and working plants while wet.",
                    "Disinfect tools and reduce plant crowding to improve airflow.",
                ],
                "prevention": [
                    "Use disease-free seed or seedlings.",
                    "Rotate away from the same crop family for at least 2 seasons where possible.",
                ],
            },
        ),
        (
            ("late_blight", "early_blight", "leaf_mold", "black_rot", "powdery_mildew", "rust", "scab", "septoria", "target_spot", "leaf_blight", "esca"),
            {
                "summary": ["Likely fungal disease symptoms were detected."],
                "treatment": [
                    "Remove infected leaves and destroy them away from the field.",
                    "Apply a crop-appropriate fungicide if disease pressure is increasing.",
                ],
                "control": [
                    "Improve spacing, pruning, and airflow around plants.",
                    "Water at soil level and avoid wetting foliage.",
                ],
                "prevention": [
                    "Rotate crops and avoid planting susceptible crops in the same location repeatedly.",
                    "Sanitize stakes, trays, and tools between seasons.",
                ],
            },
        ),
        (
            ("mosaic", "yellow_leaf_curl", "yellowleaf_curl", "virus"),
            {
                "summary": ["Likely viral disease symptoms were detected."],
                "treatment": [
                    "There is no direct cure for most plant viral infections.",
                    "Remove severely infected plants to reduce spread.",
                ],
                "control": [
                    "Control insect vectors such as whiteflies, aphids, and mites.",
                    "Remove weeds that can host virus or vectors.",
                ],
                "prevention": [
                    "Use resistant varieties where available.",
                    "Use insect netting or reflective mulch where appropriate.",
                ],
            },
        ),
        (
            ("spider_mites",),
            {
                "summary": ["Likely mite damage was detected."],
                "treatment": [
                    "Spray leaf undersides with water to reduce mite populations.",
                    "Use insecticidal soap, horticultural oil, or approved miticide if infestation persists.",
                ],
                "control": [
                    "Avoid drought stress and dusty conditions.",
                    "Preserve beneficial predators by limiting broad-spectrum insecticides.",
                ],
                "prevention": ["Inspect leaf undersides regularly during hot, dry weather."],
            },
        ),
        (
            ("haunglongbing", "citrus_greening"),
            {
                "summary": ["Likely citrus greening symptoms were detected."],
                "treatment": ["There is no reliable cure for citrus greening once a tree is infected."],
                "control": [
                    "Contact a local extension/agriculture officer for confirmation.",
                    "Manage psyllid vectors and remove confirmed infected trees where required.",
                ],
                "prevention": ["Use certified disease-free citrus planting material."],
            },
        ),
    ]

    @classmethod
    def recommendations_for(cls, label: str, confidence: float) -> dict[str, list[str]]:
        lower_label = label.lower()
        for keywords, recommendation in cls.DISEASE_RULES:
            if any(keyword in lower_label for keyword in keywords):
                return cls._with_confidence_note(recommendation, confidence)

        return cls._with_confidence_note(
            {
                "summary": ["The model detected a possible plant health issue."],
                "treatment": ["Compare symptoms with local crop guides before applying chemicals."],
                "control": ["Isolate or mark affected plants and monitor disease spread."],
                "prevention": ["Use clean tools, improve airflow, and avoid unnecessary leaf wetness."],
            },
            confidence,
        )

    @staticmethod
    def _with_confidence_note(
        recommendation: dict[str, list[str]],
        confidence: float,
    ) -> dict[str, list[str]]:
        result = {key: list(value) for key, value in recommendation.items()}
        if confidence < 0.55:
            result.setdefault("caution", []).append(
                "Prediction confidence is low. Capture a closer, sharper leaf image and confirm with an agronomist."
            )
        elif confidence < 0.75:
            result.setdefault("caution", []).append(
                "Prediction confidence is moderate. Use this as guidance, not a final diagnosis."
            )
        else:
            result.setdefault("caution", []).append(
                "Use local extension guidance before applying pesticides or removing plants."
            )
        return result


class PlantDiseaseSDK:
    """Local inference SDK for the camera/terminal demo."""

    def __init__(
        self,
        model_path: Path,
        metadata_path: Path | None = None,
        input_size: tuple[int, int] = (224, 224),
    ):
        self.model_path = model_path
        self.metadata_path = metadata_path
        self.input_size = input_size
        self.class_names = self._load_class_names(metadata_path)
        self.session = ort.InferenceSession(str(model_path), providers=self._providers())
        self.input_name = self.session.get_inputs()[0].name
        self.output_name = self.session.get_outputs()[0].name

    @staticmethod
    def _providers() -> list[str]:
        providers = ["CPUExecutionProvider"]
        if "CUDAExecutionProvider" in ort.get_available_providers():
            providers.insert(0, "CUDAExecutionProvider")
        return providers

    @staticmethod
    def _load_class_names(metadata_path: Path | None) -> list[str]:
        if not metadata_path or not metadata_path.exists():
            return []

        with metadata_path.open("r", encoding="utf-8") as file:
            metadata = json.load(file)

        class_names = metadata.get("class_names")
        if class_names:
            return list(class_names)

        classes = metadata.get("classes")
        if classes:
            return list(classes)

        return []

    def preprocess(self, image_bgr: np.ndarray) -> np.ndarray:
        image_rgb = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB)
        image_rgb = cv2.resize(image_rgb, self.input_size, interpolation=cv2.INTER_AREA)
        image = image_rgb.astype(np.float32) / 255.0
        image = (image - IMAGENET_MEAN) / IMAGENET_STD
        image = np.transpose(image, (2, 0, 1))
        return image[None, ...].astype(np.float32)

    def predict(self, image_bgr: np.ndarray, top_k: int = 5) -> PredictionResult:
        import time

        tensor = self.preprocess(image_bgr)
        start = time.perf_counter()
        logits = self.session.run([self.output_name], {self.input_name: tensor})[0][0]
        inference_time_ms = (time.perf_counter() - start) * 1000
        probabilities = softmax(logits)
        top_indices = np.argsort(probabilities)[::-1][:top_k]

        top_predictions = []
        for index in top_indices:
            label = self.class_names[index] if index < len(self.class_names) else f"class_{index}"
            top_predictions.append(
                {
                    "label": label,
                    "display_label": humanize(label),
                    "confidence": float(probabilities[index]),
                }
            )

        best = top_predictions[0]
        crop, condition = split_label(str(best["label"]))
        confidence = float(best["confidence"])
        return PredictionResult(
            label=str(best["label"]),
            crop=humanize(crop),
            condition=humanize(condition),
            confidence=confidence,
            inference_time_ms=inference_time_ms,
            top_predictions=top_predictions,
            recommendations=RecommendationEngine.recommendations_for(str(best["label"]), confidence),
        )

    def predict_file(self, image_path: Path, top_k: int = 5) -> PredictionResult:
        image = cv2.imread(str(image_path))
        if image is None:
            raise ValueError(f"Could not read image: {image_path}")
        return self.predict(image, top_k=top_k)


def result_to_dict(result: PredictionResult) -> dict[str, Any]:
    return {
        "label": result.label,
        "crop": result.crop,
        "condition": result.condition,
        "confidence": result.confidence,
        "inference_time_ms": result.inference_time_ms,
        "top_predictions": result.top_predictions,
        "recommendations": result.recommendations,
    }
