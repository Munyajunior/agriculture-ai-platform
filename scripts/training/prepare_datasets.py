#!/usr/bin/env python3
"""Prepare multi-source plant disease datasets for ImageFolder training.

The script standardizes labels, creates stratified train/val/test splits, and
writes an ImageFolder-compatible directory tree:

    output/
      train/<class>/*.jpg
      val/<class>/*.jpg
      test/<class>/*.jpg
      metadata/*.json|csv
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import logging
import random
import re
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any


LOGGER = logging.getLogger("prepare_datasets")
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}


@dataclass(frozen=True)
class Sample:
    source: str
    image_path: Path
    raw_label: str
    label: str


def normalize_label(label: str) -> str:
    """Normalize dataset labels into stable class directory names."""

    normalized = label.strip().lower()
    normalized = normalized.replace("___", "__")
    normalized = normalized.replace(" ", "_")
    normalized = normalized.replace("-", "_")
    normalized = normalized.replace("/", "_")
    normalized = normalized.replace(",", "_")
    normalized = re.sub(r"[^a-z0-9_]+", "", normalized)
    normalized = re.sub(r"_+", "_", normalized)
    normalized = normalized.strip("_")
    return normalized or "unknown"


def load_config(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def image_files(root: Path) -> list[Path]:
    return [
        path
        for path in root.rglob("*")
        if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS
    ]


def collect_image_folder(source: dict[str, Any], raw_root: Path) -> list[Sample]:
    source_root = first_existing_path(raw_root, source.get("candidate_paths", [source["path"]]))
    if not source_root.exists():
        LOGGER.warning("Skipping %s: %s does not exist", source["name"], source_root)
        return []

    samples: list[Sample] = []
    class_dirs = [path for path in source_root.iterdir() if path.is_dir()]
    if not class_dirs:
        LOGGER.warning("Skipping %s: no class directories found in %s", source["name"], source_root)
        return []

    for class_dir in class_dirs:
        raw_label = class_dir.name
        label = normalize_label(source.get("label_aliases", {}).get(raw_label, raw_label))
        for image_path in image_files(class_dir):
            samples.append(
                Sample(
                    source=source["name"],
                    image_path=image_path,
                    raw_label=raw_label,
                    label=label,
                )
            )

    return samples


def composite_multilabel(label: str) -> str:
    parts = [normalize_label(part) for part in re.split(r"[\s,;|]+", label.strip()) if part.strip()]
    return "__".join(sorted(parts)) if parts else "unknown"


def collect_csv_labels(source: dict[str, Any], raw_root: Path) -> list[Sample]:
    csv_path = first_existing_path(raw_root, source.get("candidate_csv_paths", [source["csv_path"]]))
    images_dir = first_existing_path(raw_root, source.get("candidate_images_dirs", [source["images_dir"]]))
    if not csv_path.exists():
        LOGGER.warning("Skipping %s: %s does not exist", source["name"], csv_path)
        return []
    if not images_dir.exists():
        LOGGER.warning("Skipping %s: %s does not exist", source["name"], images_dir)
        return []

    samples: list[Sample] = []
    label_map = {str(key): value for key, value in source.get("label_map", {}).items()}

    with csv_path.open("r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        for row in reader:
            image_name = row[source["image_column"]]
            raw_label = str(row[source["label_column"]])
            mapped_label = label_map.get(raw_label, raw_label)
            if source.get("multi_label_strategy") == "composite":
                label = composite_multilabel(mapped_label)
            else:
                label = normalize_label(mapped_label)

            image_path = images_dir / image_name
            if not image_path.exists():
                LOGGER.debug("Missing image for %s: %s", source["name"], image_path)
                continue

            samples.append(
                Sample(
                    source=source["name"],
                    image_path=image_path,
                    raw_label=raw_label,
                    label=label,
                )
            )

    return samples


def first_existing_path(root: Path, candidates: list[str]) -> Path:
    for candidate in candidates:
        path = root / candidate
        if path.exists():
            return path
    return root / candidates[0]


def parse_simple_yolo_names(yaml_path: Path) -> list[str]:
    """Parse the simple `names:` list from a YOLO data.yaml without PyYAML."""

    names: list[str] = []
    in_names = False
    with yaml_path.open("r", encoding="utf-8") as file:
        for line in file:
            stripped = line.strip()
            if stripped == "names:":
                in_names = True
                continue
            if in_names and stripped.startswith("- "):
                names.append(stripped[2:].strip().strip("'\""))
                continue
            if in_names and stripped and not stripped.startswith("- "):
                break
    return names


def image_label_path(image_path: Path) -> Path:
    split_dir = image_path.parent.parent
    return split_dir / "labels" / f"{image_path.stem}.txt"


def collect_yolo_detection(source: dict[str, Any], raw_root: Path) -> list[Sample]:
    source_root = raw_root / source["path"]
    yaml_path = raw_root / source.get("yaml_path", f"{source['path']}/data.yaml")
    if not source_root.exists():
        LOGGER.warning("Skipping %s: %s does not exist", source["name"], source_root)
        return []
    if not yaml_path.exists():
        LOGGER.warning("Skipping %s: %s does not exist", source["name"], yaml_path)
        return []

    class_names = parse_simple_yolo_names(yaml_path)
    if not class_names:
        LOGGER.warning("Skipping %s: no YOLO class names found in %s", source["name"], yaml_path)
        return []

    samples: list[Sample] = []
    for split in source.get("splits", ["train", "valid", "val", "test"]):
        images_dir = source_root / split / "images"
        if not images_dir.exists():
            continue

        for image_path in image_files(images_dir):
            label_path = image_label_path(image_path)
            if not label_path.exists():
                continue

            class_ids: list[int] = []
            with label_path.open("r", encoding="utf-8") as file:
                for line in file:
                    parts = line.split()
                    if not parts:
                        continue
                    try:
                        class_ids.append(int(float(parts[0])))
                    except ValueError:
                        continue

            labels = sorted(
                {
                    class_names[class_id]
                    for class_id in class_ids
                    if 0 <= class_id < len(class_names)
                }
            )
            if not labels:
                continue

            if len(labels) > 1 and source.get("multi_label_strategy") == "composite":
                raw_label = " ".join(labels)
                label = "__".join(normalize_label(label_part) for label_part in labels)
            else:
                raw_label = labels[0]
                label = normalize_label(raw_label)

            samples.append(
                Sample(
                    source=source["name"],
                    image_path=image_path,
                    raw_label=raw_label,
                    label=label,
                )
            )

    return samples


def collect_samples(config: dict[str, Any], raw_root: Path) -> list[Sample]:
    collectors = {
        "image_folder": collect_image_folder,
        "csv_labels": collect_csv_labels,
        "yolo_detection": collect_yolo_detection,
    }

    all_samples: list[Sample] = []
    for source in config["sources"]:
        if not source.get("enabled", True):
            continue
        source_type = source["type"]
        if source_type not in collectors:
            raise ValueError(f"Unsupported source type: {source_type}")
        samples = collectors[source_type](source, raw_root)
        LOGGER.info("Collected %s samples from %s", len(samples), source["name"])
        all_samples.extend(samples)

    return all_samples


def split_samples(
    samples: list[Sample],
    val_ratio: float,
    test_ratio: float,
    seed: int,
    min_samples_per_class: int,
) -> dict[str, list[Sample]]:
    by_label: dict[str, list[Sample]] = {}
    for sample in samples:
        by_label.setdefault(sample.label, []).append(sample)

    rng = random.Random(seed)
    splits = {"train": [], "val": [], "test": []}

    for label, label_samples in sorted(by_label.items()):
        if len(label_samples) < min_samples_per_class:
            LOGGER.warning(
                "Dropping class %s: only %s sample(s), minimum is %s",
                label,
                len(label_samples),
                min_samples_per_class,
            )
            continue

        rng.shuffle(label_samples)
        total = len(label_samples)
        test_count = max(1, round(total * test_ratio)) if test_ratio > 0 and total >= 3 else 0
        val_count = max(1, round(total * val_ratio)) if val_ratio > 0 and total >= 3 else 0

        if val_count + test_count >= total:
            val_count = 1 if total >= 3 else 0
            test_count = 1 if total >= 4 else 0

        splits["test"].extend(label_samples[:test_count])
        splits["val"].extend(label_samples[test_count : test_count + val_count])
        splits["train"].extend(label_samples[test_count + val_count :])

    for split_samples_ in splits.values():
        rng.shuffle(split_samples_)

    return splits


def safe_filename(sample: Sample) -> str:
    digest = hashlib.sha1(str(sample.image_path).encode("utf-8")).hexdigest()[:12]
    stem = normalize_label(sample.image_path.stem)[:48]
    return f"{sample.source}__{stem}__{digest}{sample.image_path.suffix.lower()}"


def place_file(source: Path, destination: Path, mode: str) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    if mode == "copy":
        shutil.copy2(source, destination)
    elif mode == "hardlink":
        try:
            destination.hardlink_to(source)
        except OSError:
            shutil.copy2(source, destination)
    elif mode == "symlink":
        try:
            destination.symlink_to(source.resolve())
        except OSError:
            shutil.copy2(source, destination)
    else:
        raise ValueError(f"Unsupported copy mode: {mode}")


def write_outputs(
    splits: dict[str, list[Sample]],
    output_dir: Path,
    config: dict[str, Any],
    copy_mode: str,
) -> None:
    metadata_dir = output_dir / "metadata"
    metadata_dir.mkdir(parents=True, exist_ok=True)

    labels = sorted({sample.label for split in splits.values() for sample in split})
    class_to_idx = {label: index for index, label in enumerate(labels)}

    manifest_rows: list[dict[str, str]] = []
    for split, split_samples in splits.items():
        for sample in split_samples:
            destination = output_dir / split / sample.label / safe_filename(sample)
            place_file(sample.image_path, destination, copy_mode)
            manifest_rows.append(
                {
                    "split": split,
                    "label": sample.label,
                    "class_index": str(class_to_idx[sample.label]),
                    "source": sample.source,
                    "raw_label": sample.raw_label,
                    "original_path": str(sample.image_path),
                    "prepared_path": str(destination),
                }
            )

    with (metadata_dir / "class_to_idx.json").open("w", encoding="utf-8") as file:
        json.dump(class_to_idx, file, indent=2, sort_keys=True)

    with (metadata_dir / "dataset_sources.resolved.json").open("w", encoding="utf-8") as file:
        json.dump(config, file, indent=2)

    with (metadata_dir / "manifest.csv").open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(
            file,
            fieldnames=[
                "split",
                "label",
                "class_index",
                "source",
                "raw_label",
                "original_path",
                "prepared_path",
            ],
        )
        writer.writeheader()
        writer.writerows(manifest_rows)

    summary = {
        "version": config.get("version", "unknown"),
        "num_classes": len(labels),
        "num_samples": len(manifest_rows),
        "splits": {split: len(samples) for split, samples in splits.items()},
        "classes": labels,
        "sources": sorted({row["source"] for row in manifest_rows}),
    }
    with (metadata_dir / "dataset_card.json").open("w", encoding="utf-8") as file:
        json.dump(summary, file, indent=2)

    LOGGER.info("Prepared dataset at %s", output_dir)
    LOGGER.info("Samples by split: %s", summary["splits"])
    LOGGER.info("Classes: %s", summary["num_classes"])


def log_sample_summary(samples: list[Sample]) -> None:
    by_source: dict[str, int] = {}
    by_label: dict[str, int] = {}
    for sample in samples:
        by_source[sample.source] = by_source.get(sample.source, 0) + 1
        by_label[sample.label] = by_label.get(sample.label, 0) + 1

    LOGGER.info("Collected %s total sample(s)", len(samples))
    LOGGER.info("Samples by source: %s", by_source)
    LOGGER.info("Discovered %s class label(s)", len(by_label))
    for label, count in sorted(by_label.items(), key=lambda item: item[1], reverse=True)[:30]:
        LOGGER.info("  %s: %s", label, count)


def main() -> None:
    parser = argparse.ArgumentParser(description="Prepare plant disease datasets for training")
    parser.add_argument(
        "--dataset-root",
        "--raw-root",
        dest="raw_root",
        type=Path,
        default=Path("datasets/raw"),
        help="Folder that contains the downloaded dataset files. Defaults to ./datasets/raw.",
    )
    parser.add_argument("--output-dir", type=Path, default=Path("data/processed/plant-disease-v1"))
    parser.add_argument("--config", type=Path, default=Path("scripts/training/dataset_sources.json"))
    parser.add_argument("--val-ratio", type=float, default=0.15)
    parser.add_argument("--test-ratio", type=float, default=0.10)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--min-samples-per-class", type=int, default=3)
    parser.add_argument("--copy-mode", choices=["copy", "hardlink", "symlink"], default="copy")
    parser.add_argument("--clean", action="store_true", help="Delete the output directory before preparing")
    parser.add_argument("--dry-run", action="store_true", help="Collect and split samples without writing files")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    if args.clean and args.output_dir.exists():
        shutil.rmtree(args.output_dir)

    config = load_config(args.config)
    samples = collect_samples(config, args.raw_root)
    if not samples:
        raise SystemExit(
            "No samples found. Check the dataset folder layout and scripts/training/dataset_sources.json."
        )
    log_sample_summary(samples)

    splits = split_samples(
        samples=samples,
        val_ratio=args.val_ratio,
        test_ratio=args.test_ratio,
        seed=args.seed,
        min_samples_per_class=args.min_samples_per_class,
    )
    if args.dry_run:
        LOGGER.info("Dry run complete. Split counts: %s", {key: len(value) for key, value in splits.items()})
        return
    write_outputs(splits, args.output_dir, config, args.copy_mode)


if __name__ == "__main__":
    main()
