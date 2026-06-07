# Model Training

This guide starts the model-training work for the plant disease classifier. The first training target is a robust single-label image classifier that can later be exported to ONNX and registered with the backend model registry.

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
PlantDoc prepared successfully:
  samples: 2,545
  classes: 29
  train: 1,910
  val: 381
  test: 254

PlantVillage, Plant Pathology 2021, and Cassava are still skipped until their configured folders/files exist under datasets/raw.
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

Run a quick CPU/GPU smoke training pass:

```powershell
uv run --package ai-service python scripts\training\train.py `
  --data_dir data\processed\plant-disease-v1 `
  --epochs 1 `
  --batch_size 16 `
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

## Export To ONNX

```powershell
uv run --package ai-service python scripts\training\export_onnx.py `
  --model_path models\plant-disease-v1\best_model.pth `
  --output_path models\plant-disease-v1\plant_disease_mobilenetv3.onnx `
  --quantize
```

The exporter reads `num_classes` from the checkpoint when available.

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
