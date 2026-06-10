# Model Training

This guide starts the model-training work for the plant disease classifier. The first training target is a robust single-label image classifier that can later be exported to ONNX and registered with the backend model registry.

For the complete command list covering dataset preparation, versioned training, evaluation, ONNX export, infrastructure, backend, Compose, and migrations, use [Project Runbook](../RUNBOOK.md).

## Dataset Plan

Use these datasets for the first serious training cycle:

| Dataset | Role | Why It Matters |
| --- | --- | --- |
| PlantVillage | Main baseline | Large, clean, class-organized plant disease dataset. Good for learning core visual disease features. |
| PlantDoc | Field robustness | Real-world backgrounds, varied lighting, occlusion, and less curated mobile-style images. |
| Plant Pathology 2021 | Field apple disease | High-quality apple foliar disease images with natural field variation and multi-label disease combinations. |
| Cassava Leaf Disease | Regional relevance | Important crop for African agriculture, with field-style cassava disease imagery. |

Do not blindly merge labels by display name. The preparation script keeps a metadata manifest with source dataset, raw label, normalized class label, and prepared file path so we can audit the final training data.

## Expected Dataset Layout

Use the existing `datasets/raw` folder. The preparation script reads from `datasets/raw` by default, so you do not need to move files into another location.

```text
datasets/
  raw/
    plantvillage/
      color/
        Tomato___Late_blight/
        Tomato___healthy/
        ...
    plantdoc/
      data.yaml
      train/images/
      train/labels/
      valid/images/
      valid/labels/
      test/images/
      test/labels/
    plant-pathology-2021/
      train.csv
      train_images/
    cassava-leaf-disease-classification/
      train.csv
      train_images/
```

If Kaggle extracts a different folder structure, update:

```text
scripts/training/dataset_sources.json
```

Every path in `dataset_sources.json` is relative to the dataset root. For example:

```json
{
  "path": "plantvillage/color"
}
```

means:

```text
datasets/raw/plantvillage/color
```

## Prepare Dataset

Create an ImageFolder-compatible dataset from `datasets/raw`:

```powershell
uv run python scripts\training\prepare_datasets.py --clean
```

Current detected state:

```text
Detected raw sources:
  PlantVillage: 20,638 samples
  PlantDoc: 2,554 samples
  Cassava: 21,397 samples
  Plant leaf disease without augmentation: 55,448 samples
  Plant leaf disease with augmentation: 61,486 samples

Dry-run total:
  samples before rare-class drops: 161,523
  classes before rare-class drops: 79

Prepared output:
  samples: 161,514
  classes: 72
  train: 121,138
  val: 24,228
  test: 16,148
```

To point at a different existing folder:

```powershell
uv run python scripts\training\prepare_datasets.py --dataset-root path\to\existing\raw-datasets --clean
```

Default output:

```text
data/processed/plant-disease-v1/
  train/<class>/*.jpg
  val/<class>/*.jpg
  test/<class>/*.jpg
  metadata/
    class_to_idx.json
    dataset_card.json
    dataset_sources.resolved.json
    manifest.csv
```

Use hardlinks instead of copies to save disk space:

```powershell
uv run python scripts\training\prepare_datasets.py --clean --copy-mode hardlink
```

## Train Baseline Model

Check the PyTorch device setup:

```powershell
uv run --package ai-service python scripts\training\check_torch.py
```

Install the CUDA PyTorch build when needed. CUDA PyTorch still runs on CPU when CUDA is unavailable, so this is the default build for training machines:

```powershell
# CUDA builds for machines with a supported modern NVIDIA GPU and driver
powershell -ExecutionPolicy Bypass -File scripts\training\setup_torch.ps1 -Variant cu118
powershell -ExecutionPolicy Bypass -File scripts\training\setup_torch.ps1 -Variant cu126
powershell -ExecutionPolicy Bypass -File scripts\training\setup_torch.ps1 -Variant cu128

# Cloud/production GPU setup: fail if CUDA is not available after install
powershell -ExecutionPolicy Bypass -File scripts\training\setup_torch.ps1 -Variant cu128 -RequireCuda
```

A CUDA-enabled PyTorch build still falls back to CPU when CUDA is unavailable. Do not install separate CPU and GPU PyTorch builds at the same time; install the CUDA build, and the training code selects the available device.

For modern GPU/cloud training:

1. Provision a machine with a supported NVIDIA GPU and recent driver.
2. Run `uv sync --all-packages`.
3. Install the CUDA PyTorch wheel that matches the platform:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\training\setup_torch.ps1 -Variant cu128 -RequireCuda
```

4. Confirm:

```powershell
uv run --package ai-service python scripts\training\check_torch.py
```

Expected GPU-ready output includes:

```text
cuda_available=True
cuda_device_count=1
training_device_auto=cuda
```

5. Train with automatic device selection:

```powershell
uv run --package ai-service python scripts\training\train.py `
  --data_dir data\processed\plant-disease-v2 `
  --epochs 1 `
  --batch_size 32 `
  --device auto `
  --output_dir models\plant-disease-v2
```

Use `--device cuda` on cloud jobs when you want the process to fail instead of silently falling back to CPU.

Run a quick CPU/GPU smoke training pass:

```powershell
uv run --package ai-service python scripts\training\train.py `
  --data_dir data\processed\plant-disease-v1 `
  --epochs 1 `
  --batch_size 16 `
  --device auto `
  --output_dir models\plant-disease-v1
```

Run a fuller first baseline:

```powershell
uv run --package ai-service python scripts\training\train.py `
  --data_dir data\processed\plant-disease-v1 `
  --epochs 30 `
  --batch_size 32 `
  --lr 0.001 `
  --output_dir models\plant-disease-v1
```

The trainer writes:

```text
models/plant-disease-v1/
  best_model.pth
  metadata.json
```

Current baseline run:

```text
model: mobilenetv3
epochs: 1
batch size: 16
train samples: 121,138
validation samples: 24,228
classes: 72
train loss: 0.3589
train accuracy: 89.23%
validation loss: 0.2634
validation accuracy: 92.28%
checkpoint: models/plant-disease-v1/best_model.pth
metadata: models/plant-disease-v1/metadata.json
```

## Export To ONNX

```powershell
uv run --package ai-service python scripts\training\export_onnx.py `
  --model_path models\plant-disease-v1\best_model.pth `
  --output_path models\plant-disease-v1\plant_disease_mobilenetv3.onnx `
  --quantize
```

The exporter reads `num_classes` from the checkpoint when available.

Current export result:

```text
fp32 onnx: models/plant-disease-v1/plant_disease_mobilenetv3.onnx
fp32 exporter: dynamo
fp32 onnx graph size: 0.34 MB
fp32 external data: models/plant-disease-v1/plant_disease_mobilenetv3.onnx.data
fp32 external data size: 15.38 MB
quantized onnx: models/plant-disease-v1/plant_disease_mobilenetv3.quant.onnx
quantized from exporter: legacy fallback after ONNX Runtime rejected dynamo graph quantization
quantized size: 4.05 MB
validated output shape: (1, 72)
metadata: models/plant-disease-v1/plant_disease_mobilenetv3.export.json
```

For production FP32 ONNX deployment, keep the `.onnx` file and its `.onnx.data` file together. The quantized ONNX is a single-file artifact.

## Evaluate Model

Evaluate the quantized ONNX model on the held-out test split:

```powershell
uv run --package ai-service python scripts\training\evaluate.py `
  --model_path models\plant-disease-v1\plant_disease_mobilenetv3.quant.onnx `
  --model_type onnx `
  --data_dir data\processed\plant-disease-v1 `
  --split test `
  --batch_size 32 `
  --output_dir models\plant-disease-v1
```

The evaluator writes:

```text
models/plant-disease-v1/evaluation.json
models/plant-disease-v1/classification_report.csv
models/plant-disease-v1/confusion_matrix.csv
models/plant-disease-v1/source_metrics.csv
```

Current held-out test result:

```text
model: models/plant-disease-v1/best_model.pth
split: test
samples: 16,148
classes: 72
accuracy: 92.35%
top-5 accuracy: 98.93%
macro F1: 60.44%
```

Source-level accuracy:

```text
plantvillage: 97.04%  (1,999 / 2,060)
plant_leaf_disease: 96.33%  (5,378 / 5,583)
plant_leaf_disease_augmented: 96.14%  (5,875 / 6,111)
cassava_leaf_disease: 74.96%  (1,605 / 2,141)
plantdoc: 21.74%  (55 / 253)
```

The low PlantDoc score is expected for this first merged-label baseline because PlantDoc is field-style detection data with labels such as `apple_leaf`, while the larger image-folder datasets use labels such as `apple_healthy`, `apple_black_rot`, and `apple_apple_scab`. The next quality pass should normalize the taxonomy and evaluate field images separately before production promotion.

## Important Training Notes

- Plant Pathology 2021 is multi-label. The current single-label baseline converts multi-label rows into composite class names such as `complex__rust`. Later, we should add a true multi-label head if that becomes part of product requirements.
- PlantDoc is smaller but important. Keep it in validation/test analysis even if its training contribution is small.
- Use the `metadata/manifest.csv` file to inspect class balance before long training runs.
- The model should not be promoted to production just because validation accuracy is high on PlantVillage. Field-image performance matters more.

## Next Improvements

- Add per-source metrics so we can see PlantVillage accuracy separately from PlantDoc/Cassava/Plant Pathology accuracy.
- Add class-balanced sampling for rare classes.
- Add confusion matrix and classification report output.
- Add true multi-label training support for Plant Pathology.
- Add model-registry registration after successful export.
