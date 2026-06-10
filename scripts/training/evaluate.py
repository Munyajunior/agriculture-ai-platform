#!/usr/bin/env python3
"""Evaluate a trained plant disease model on an ImageFolder split."""

from __future__ import annotations

import argparse
import csv
import json
import logging
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import onnxruntime as ort
import torch
from torch.utils.data import DataLoader, Subset
from torchvision import datasets, transforms
from tqdm import tqdm

try:
    from model_utils import load_checkpoint_model
except ModuleNotFoundError:
    from scripts.training.model_utils import load_checkpoint_model


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def build_transform() -> transforms.Compose:
    return transforms.Compose(
        [
            transforms.Resize((224, 224)),
            transforms.ToTensor(),
            transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225]),
        ]
    )


def load_manifest_sources(data_dir: Path) -> dict[str, str]:
    manifest_path = data_dir / "metadata" / "manifest.csv"
    if not manifest_path.exists():
        return {}

    sources: dict[str, str] = {}
    with manifest_path.open("r", encoding="utf-8", newline="") as file:
        reader = csv.DictReader(file)
        for row in reader:
            prepared_path = Path(row["prepared_path"])
            sources[str(prepared_path)] = row["source"]
            sources[str(prepared_path.resolve())] = row["source"]
    return sources


class TorchPredictor:
    def __init__(self, model_path: Path, device: str):
        self.device = torch.device(device)
        self.model, self.checkpoint = load_checkpoint_model(model_path, device=self.device)

    def predict(self, images: torch.Tensor) -> np.ndarray:
        with torch.no_grad():
            outputs = self.model(images.to(self.device))
        return outputs.detach().cpu().numpy()


class OnnxPredictor:
    def __init__(self, model_path: Path):
        self.session = ort.InferenceSession(str(model_path))
        input_meta = self.session.get_inputs()[0]
        self.input_name = input_meta.name
        self.output_name = self.session.get_outputs()[0].name
        batch_dim = input_meta.shape[0]
        self.fixed_batch_size = batch_dim if isinstance(batch_dim, int) and batch_dim > 0 else None

    def predict(self, images: torch.Tensor) -> np.ndarray:
        batch = images.detach().cpu().numpy().astype(np.float32)
        if self.fixed_batch_size and batch.shape[0] != self.fixed_batch_size:
            outputs = []
            for start in range(0, batch.shape[0], self.fixed_batch_size):
                chunk = batch[start : start + self.fixed_batch_size]
                if chunk.shape[0] != self.fixed_batch_size:
                    chunk_outputs = [
                        self.session.run([self.output_name], {self.input_name: item[None, ...]})[0]
                        for item in chunk
                    ]
                    outputs.extend(chunk_outputs)
                    continue
                outputs.append(self.session.run([self.output_name], {self.input_name: chunk})[0])
            return np.concatenate(outputs, axis=0)
        return self.session.run([self.output_name], {self.input_name: batch})[0]


def top_k_correct(logits: np.ndarray, labels: np.ndarray, k: int) -> int:
    if logits.shape[1] < k:
        k = logits.shape[1]
    top_indices = np.argpartition(logits, -k, axis=1)[:, -k:]
    return int(sum(label in row for label, row in zip(labels, top_indices, strict=False)))


def compute_metrics(confusion: np.ndarray, class_names: list[str]) -> list[dict[str, float | int | str]]:
    rows: list[dict[str, float | int | str]] = []
    for index, class_name in enumerate(class_names):
        tp = int(confusion[index, index])
        fp = int(confusion[:, index].sum() - tp)
        fn = int(confusion[index, :].sum() - tp)
        support = int(confusion[index, :].sum())
        precision = tp / (tp + fp) if tp + fp else 0.0
        recall = tp / (tp + fn) if tp + fn else 0.0
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
        rows.append(
            {
                "class_index": index,
                "class_name": class_name,
                "precision": precision,
                "recall": recall,
                "f1": f1,
                "support": support,
            }
        )
    return rows


def write_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        return
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def write_confusion_matrix(path: Path, confusion: np.ndarray, class_names: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.writer(file)
        writer.writerow(["actual\\predicted", *class_names])
        for class_name, row in zip(class_names, confusion.tolist(), strict=False):
            writer.writerow([class_name, *row])


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate plant disease classifier")
    parser.add_argument("--data_dir", type=Path, default=Path("data/processed/plant-disease-v1"))
    parser.add_argument("--split", choices=["train", "val", "test"], default="test")
    parser.add_argument("--model_path", type=Path, required=True)
    parser.add_argument("--model_type", choices=["torch", "onnx"], default="onnx")
    parser.add_argument("--batch_size", type=int, default=32)
    parser.add_argument("--num_workers", type=int, default=4)
    parser.add_argument("--device", default="cuda" if torch.cuda.is_available() else "cpu")
    parser.add_argument("--output_dir", type=Path, default=Path("models/plant-disease-v1"))
    parser.add_argument("--max_samples", type=int, default=None)
    args = parser.parse_args()

    dataset = datasets.ImageFolder(args.data_dir / args.split, transform=build_transform())
    if args.max_samples:
        dataset = Subset(dataset, list(range(min(args.max_samples, len(dataset)))))

    loader = DataLoader(
        dataset,
        batch_size=args.batch_size,
        shuffle=False,
        num_workers=args.num_workers,
    )

    class_names = dataset.dataset.classes if isinstance(dataset, Subset) else dataset.classes
    samples = dataset.dataset.samples if isinstance(dataset, Subset) else dataset.samples
    if isinstance(dataset, Subset):
        samples = [samples[index] for index in dataset.indices]

    predictor = (
        TorchPredictor(args.model_path, args.device)
        if args.model_type == "torch"
        else OnnxPredictor(args.model_path)
    )

    source_lookup = load_manifest_sources(args.data_dir)
    num_classes = len(class_names)
    confusion = np.zeros((num_classes, num_classes), dtype=np.int64)
    source_counts: dict[str, dict[str, int]] = defaultdict(lambda: {"correct": 0, "total": 0})

    total = 0
    correct_top1 = 0
    correct_top5 = 0
    sample_offset = 0

    for images, labels_tensor in tqdm(loader, desc=f"Evaluating {args.split}"):
        labels = labels_tensor.numpy()
        logits = predictor.predict(images)
        predictions = logits.argmax(axis=1)

        total += len(labels)
        correct_top1 += int((predictions == labels).sum())
        correct_top5 += top_k_correct(logits, labels, 5)

        for actual, predicted in zip(labels, predictions, strict=False):
            confusion[int(actual), int(predicted)] += 1

        batch_samples = samples[sample_offset : sample_offset + len(labels)]
        for sample, actual, predicted in zip(batch_samples, labels, predictions, strict=False):
            source = source_lookup.get(str(Path(sample[0]).resolve()), "unknown")
            source_counts[source]["total"] += 1
            if int(actual) == int(predicted):
                source_counts[source]["correct"] += 1
        sample_offset += len(labels)

    class_rows = compute_metrics(confusion, class_names)
    supported_class_rows = [row for row in class_rows if int(row["support"]) > 0]
    macro_f1 = sum(float(row["f1"]) for row in class_rows) / len(class_rows)
    supported_macro_f1 = (
        sum(float(row["f1"]) for row in supported_class_rows) / len(supported_class_rows)
        if supported_class_rows
        else 0.0
    )
    accuracy = correct_top1 / total if total else 0.0
    top5_accuracy = correct_top5 / total if total else 0.0

    source_rows = [
        {
            "source": source,
            "accuracy": values["correct"] / values["total"] if values["total"] else 0.0,
            "correct": values["correct"],
            "total": values["total"],
        }
        for source, values in sorted(source_counts.items())
    ]

    summary = {
        "evaluated_at": datetime.now(UTC).isoformat(),
        "model_path": str(args.model_path),
        "model_type": args.model_type,
        "data_dir": str(args.data_dir),
        "split": args.split,
        "num_samples": total,
        "num_classes": num_classes,
        "accuracy": accuracy,
        "top5_accuracy": top5_accuracy,
        "macro_f1": macro_f1,
        "supported_macro_f1": supported_macro_f1,
        "class_names": class_names,
        "source_metrics": source_rows,
    }

    args.output_dir.mkdir(parents=True, exist_ok=True)
    evaluation_path = args.output_dir / "evaluation.json"
    with evaluation_path.open("w", encoding="utf-8") as file:
        json.dump(summary, file, indent=2)

    write_csv(args.output_dir / "classification_report.csv", class_rows)
    write_csv(args.output_dir / "source_metrics.csv", source_rows)
    write_confusion_matrix(args.output_dir / "confusion_matrix.csv", confusion, class_names)

    logger.info("Evaluation written to %s", evaluation_path)
    logger.info(
        "Accuracy: %.4f, Top-5: %.4f, Macro F1: %.4f, Supported Macro F1: %.4f",
        accuracy,
        top5_accuracy,
        macro_f1,
        supported_macro_f1,
    )


if __name__ == "__main__":
    main()
