#!/usr/bin/env python3
"""Desktop/terminal camera demo for plant disease detection."""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

import cv2

from plant_disease_sdk import PlantDiseaseSDK, result_to_dict


DEFAULT_MODEL = Path("models/plant-disease-v1/plant_disease_mobilenetv3.quant.onnx")
DEFAULT_METADATA = Path("models/plant-disease-v1/plant_disease_mobilenetv3.export.json")


def print_result(result) -> None:
    print("\n=== Plant Disease Prediction ===")
    print(f"Crop: {result.crop}")
    print(f"Condition: {result.condition}")
    print(f"Confidence: {result.confidence:.2%}")
    print(f"Inference: {result.inference_time_ms:.1f} ms")

    print("\nTop predictions:")
    for item in result.top_predictions:
        print(f"  - {item['display_label']}: {float(item['confidence']):.2%}")

    print("\nRecommendations:")
    for section, items in result.recommendations.items():
        print(f"  {section.title()}:")
        for item in items:
            print(f"    - {item}")


def save_report(result, image_path: Path | None, output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
    report_path = output_dir / f"plant_diagnosis_{timestamp}.json"
    payload = result_to_dict(result)
    payload["image_path"] = str(image_path) if image_path else None
    payload["created_at"] = datetime.now(UTC).isoformat()
    with report_path.open("w", encoding="utf-8") as file:
        json.dump(payload, file, indent=2)
    return report_path


def annotate_frame(frame, result):
    annotated = frame.copy()
    text = f"{result.crop}: {result.condition} ({result.confidence:.1%})"
    cv2.rectangle(annotated, (0, 0), (annotated.shape[1], 48), (0, 0, 0), -1)
    cv2.putText(
        annotated,
        text,
        (12, 32),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.75,
        (255, 255, 255),
        2,
        cv2.LINE_AA,
    )
    return annotated


def run_image_mode(args) -> None:
    sdk = PlantDiseaseSDK(args.model, args.metadata)
    result = sdk.predict_file(args.image, top_k=args.top_k)
    print_result(result)
    report_path = save_report(result, args.image, args.output_dir)
    print(f"\nReport saved: {report_path}")


def run_camera_mode(args) -> None:
    sdk = PlantDiseaseSDK(args.model, args.metadata)
    capture = cv2.VideoCapture(args.camera)
    if not capture.isOpened():
        raise RuntimeError(f"Could not open camera index {args.camera}")

    print("Camera controls:")
    print("  c or space: capture and diagnose")
    print("  q or esc: quit")

    last_result = None
    while True:
        ok, frame = capture.read()
        if not ok:
            raise RuntimeError("Camera frame read failed")

        display = frame
        if last_result:
            display = annotate_frame(frame, last_result)

        cv2.imshow("Agriculture AI - Plant Disease Demo", display)
        key = cv2.waitKey(1) & 0xFF

        if key in (ord("q"), 27):
            break

        if key in (ord("c"), 32):
            timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
            args.output_dir.mkdir(parents=True, exist_ok=True)
            image_path = args.output_dir / f"capture_{timestamp}.jpg"
            cv2.imwrite(str(image_path), frame)
            last_result = sdk.predict(frame, top_k=args.top_k)
            print_result(last_result)
            report_path = save_report(last_result, image_path, args.output_dir)
            print(f"\nCapture saved: {image_path}")
            print(f"Report saved: {report_path}")

    capture.release()
    cv2.destroyAllWindows()


def main() -> None:
    parser = argparse.ArgumentParser(description="Plant disease desktop camera demo")
    parser.add_argument("--model", type=Path, default=DEFAULT_MODEL)
    parser.add_argument("--metadata", type=Path, default=DEFAULT_METADATA)
    parser.add_argument("--camera", type=int, default=0)
    parser.add_argument("--image", type=Path, default=None, help="Run once on an image instead of opening camera")
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--output-dir", type=Path, default=Path("demo-output"))
    args = parser.parse_args()

    if args.image:
        run_image_mode(args)
    else:
        run_camera_mode(args)


if __name__ == "__main__":
    main()
