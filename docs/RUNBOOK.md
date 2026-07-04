# Project Runbook

This runbook collects the commands used to prepare datasets, train/evaluate model versions, export artifacts, run infrastructure, run backend services, use Docker Compose, and manage migrations.

Run commands from the repository root:

```powershell
cd J:\projects\agriculture-ai-platform
```

## Install Project

Create/update the Python environment:

```powershell
uv sync --all-packages
```

Repair a broken virtual environment:

```powershell
uv venv --clear
uv sync --all-packages
```

Check Git status:

```powershell
git status --short
```

## PyTorch Setup

Check current PyTorch/device state:

```powershell
uv run --package ai-service python scripts\training\check_torch.py
```

Install CUDA PyTorch. This is the default training build; it still falls back to CPU when CUDA is unavailable:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\training\setup_torch.ps1 -Variant cu128
```

Other CUDA variants:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\training\setup_torch.ps1 -Variant cu118 -RequireCuda
powershell -ExecutionPolicy Bypass -File scripts\training\setup_torch.ps1 -Variant cu126 -RequireCuda
```

Cloud/production GPU setup should require CUDA after install:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\training\setup_torch.ps1 -Variant cu128 -RequireCuda
```

Expected GPU-ready output:

```text
cuda_available=True
cuda_device_count=1
training_device_auto=cuda
```

Use `--device auto` for normal training. Use `--device cuda` on cloud jobs when training should fail if CUDA is not available.

## Dataset Preparation

Raw datasets live under:

```text
datasets/raw
```

Dataset source config:

```text
scripts/training/dataset_sources.json
```

Dry-run dataset discovery:

```powershell
uv run python scripts\training\prepare_datasets.py --dry-run
```

Prepare the current default dataset version:

```powershell
uv run python scripts\training\prepare_datasets.py --copy-mode hardlink --clean
```

Prepare a specific output version:

```powershell
uv run python scripts\training\prepare_datasets.py `
  --output-dir data\processed\plant-disease-v2 `
  --copy-mode hardlink `
  --clean
```

Prepare a future version, for example `v3`:

```powershell
uv run python scripts\training\prepare_datasets.py `
  --output-dir data\processed\plant-disease-v3 `
  --copy-mode hardlink `
  --clean
```

Use a different raw dataset root:

```powershell
uv run python scripts\training\prepare_datasets.py `
  --dataset-root D:\datasets\agriculture `
  --output-dir data\processed\plant-disease-v3 `
  --copy-mode hardlink `
  --clean
```

Inspect prepared dataset metadata:

```powershell
Get-Content data\processed\plant-disease-v2\metadata\dataset_card.json
Get-Content data\processed\plant-disease-v2\metadata\class_to_idx.json
```

Prepared dataset layout:

```text
data/processed/plant-disease-v2/
  train/<class>/*.jpg
  val/<class>/*.jpg
  test/<class>/*.jpg
  metadata/
    class_to_idx.json
    dataset_card.json
    dataset_sources.resolved.json
    manifest.csv
```

## Train Model Versions

Quick one-epoch smoke training for `v2`:

```powershell
uv run --package ai-service python scripts\training\train.py `
  --data_dir data\processed\plant-disease-v2 `
  --epochs 1 `
  --batch_size 16 `
  --device auto `
  --output_dir models\plant-disease-v2
```

GPU/cloud training for `v2`:

```powershell
uv run --package ai-service python scripts\training\train.py `
  --data_dir data\processed\plant-disease-v2 `
  --epochs 1 `
  --batch_size 32 `
  --device cuda `
  --output_dir models\plant-disease-v2
```

Fuller training for `v2`:

```powershell
uv run --package ai-service python scripts\training\train.py `
  --data_dir data\processed\plant-disease-v2 `
  --epochs 30 `
  --batch_size 32 `
  --lr 0.001 `
  --device auto `
  --output_dir models\plant-disease-v2
```

Train a future `v3` model:

```powershell
uv run --package ai-service python scripts\training\train.py `
  --data_dir data\processed\plant-disease-v3 `
  --epochs 30 `
  --batch_size 32 `
  --lr 0.001 `
  --device auto `
  --output_dir models\plant-disease-v3
```

Use fewer workers on slow Windows machines:

```powershell
uv run --package ai-service python scripts\training\train.py `
  --data_dir data\processed\plant-disease-v2 `
  --epochs 1 `
  --batch_size 16 `
  --num_workers 0 `
  --device auto `
  --output_dir models\plant-disease-v2
```

Training outputs:

```text
models/plant-disease-v2/
  best_model.pth
  metadata.json
```

## Export Model Versions

Export `v2` to ONNX with quantization:

```powershell
uv run --package ai-service python scripts\training\export_onnx.py `
  --model_path models\plant-disease-v2\best_model.pth `
  --output_path models\plant-disease-v2\plant_disease_mobilenetv3.onnx `
  --exporter dynamo `
  --quantization-exporter auto `
  --quantize
```

Export `v3`:

```powershell
uv run --package ai-service python scripts\training\export_onnx.py `
  --model_path models\plant-disease-v3\best_model.pth `
  --output_path models\plant-disease-v3\plant_disease_mobilenetv3.onnx `
  --exporter dynamo `
  --quantization-exporter auto `
  --quantize
```

Force legacy export:

```powershell
uv run --package ai-service python scripts\training\export_onnx.py `
  --model_path models\plant-disease-v2\best_model.pth `
  --output_path models\plant-disease-v2\plant_disease_mobilenetv3.legacy.onnx `
  --exporter legacy
```

Export with dynamic batch:

```powershell
uv run --package ai-service python scripts\training\export_onnx.py `
  --model_path models\plant-disease-v2\best_model.pth `
  --output_path models\plant-disease-v2\plant_disease_mobilenetv3.dynamic.onnx `
  --exporter dynamo `
  --dynamic-batch
```

Expected export outputs:

```text
models/plant-disease-v2/
  plant_disease_mobilenetv3.onnx
  plant_disease_mobilenetv3.onnx.data
  plant_disease_mobilenetv3.quant.onnx
  plant_disease_mobilenetv3.export.json
```

The dynamo FP32 export may use external data, so deploy the `.onnx` and `.onnx.data` files together. The quantized ONNX artifact is single-file.

## Evaluate Model Versions

Evaluate PyTorch checkpoint on test split:

```powershell
uv run --package ai-service python scripts\training\evaluate.py `
  --model_path models\plant-disease-v2\best_model.pth `
  --model_type torch `
  --data_dir data\processed\plant-disease-v2 `
  --split test `
  --batch_size 32 `
  --output_dir models\plant-disease-v2
```

Evaluate quantized ONNX:

```powershell
uv run --package ai-service python scripts\training\evaluate.py `
  --model_path models\plant-disease-v2\plant_disease_mobilenetv3.quant.onnx `
  --model_type onnx `
  --data_dir data\processed\plant-disease-v2 `
  --split test `
  --batch_size 32 `
  --output_dir models\plant-disease-v2
```

Fast smoke evaluation:

```powershell
uv run --package ai-service python scripts\training\evaluate.py `
  --model_path models\plant-disease-v2\best_model.pth `
  --model_type torch `
  --data_dir data\processed\plant-disease-v2 `
  --split test `
  --batch_size 32 `
  --max_samples 256 `
  --output_dir models\plant-disease-v2\eval-smoke
```

Evaluation outputs:

```text
models/plant-disease-v2/
  evaluation.json
  classification_report.csv
  confusion_matrix.csv
  source_metrics.csv
```

## Versioning Workflow

Use this pattern for each new model version:

```powershell
$Version = "v3"
$DataDir = "data\processed\plant-disease-$Version"
$ModelDir = "models\plant-disease-$Version"
```

Prepare:

```powershell
uv run python scripts\training\prepare_datasets.py `
  --output-dir $DataDir `
  --copy-mode hardlink `
  --clean
```

Train:

```powershell
uv run --package ai-service python scripts\training\train.py `
  --data_dir $DataDir `
  --epochs 30 `
  --batch_size 32 `
  --device auto `
  --output_dir $ModelDir
```

Export:

```powershell
uv run --package ai-service python scripts\training\export_onnx.py `
  --model_path "$ModelDir\best_model.pth" `
  --output_path "$ModelDir\plant_disease_mobilenetv3.onnx" `
  --exporter dynamo `
  --quantization-exporter auto `
  --quantize
```

Evaluate:

```powershell
uv run --package ai-service python scripts\training\evaluate.py `
  --model_path "$ModelDir\best_model.pth" `
  --model_type torch `
  --data_dir $DataDir `
  --split test `
  --batch_size 32 `
  --output_dir $ModelDir
```

Compare source metrics:

```powershell
Get-Content models\plant-disease-v1\source_metrics.csv
Get-Content models\plant-disease-v2\source_metrics.csv
Get-Content models\plant-disease-v3\source_metrics.csv
```

Compare evaluation summaries:

```powershell
Get-Content models\plant-disease-v1\evaluation.json
Get-Content models\plant-disease-v2\evaluation.json
Get-Content models\plant-disease-v3\evaluation.json
```

## Infrastructure

Start infrastructure only:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\setup_infrastructure.ps1
```

Reset local infrastructure volumes, then start:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\setup_infrastructure.ps1 -ResetVolumes
```

Start infrastructure and backend service containers:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\setup_infrastructure.ps1 -Services
```

Build backend images, then start services:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\setup_infrastructure.ps1 -Services -Build
```

One-command local backend run:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\run_backend_local.ps1
```

Keep that terminal open while using the API in a browser. It starts infrastructure, checks each backend service, then keeps ports `8000` through `8006` running until `Ctrl+C`.

Expected infrastructure ports:

```text
PostgreSQL: 127.0.0.1:15432
Redis: 127.0.0.1:6380
MinIO API: http://localhost:9000
MinIO Console: http://localhost:9001
```

## Docker Compose

Compose file:

```text
infrastructure/docker/docker-compose.yaml
```

Validate Compose:

```powershell
docker compose --env-file .env -f infrastructure\docker\docker-compose.yaml config --quiet
```

Start infrastructure:

```powershell
docker compose --env-file .env -f infrastructure\docker\docker-compose.yaml up -d postgres redis minio
```

Start backend services:

```powershell
docker compose --env-file .env -f infrastructure\docker\docker-compose.yaml up -d api-gateway auth-service ai-service analytics-service media-service model-registry sync-service
```

Build and start backend services:

```powershell
docker compose --env-file .env -f infrastructure\docker\docker-compose.yaml up -d --build api-gateway auth-service ai-service analytics-service media-service model-registry sync-service
```

Start proxy and observability:

```powershell
docker compose --env-file .env -f infrastructure\docker\docker-compose.yaml up -d nginx prometheus grafana
```

Show running containers:

```powershell
docker ps
```

Follow backend logs:

```powershell
docker compose --env-file .env -f infrastructure\docker\docker-compose.yaml logs -f api-gateway auth-service ai-service analytics-service media-service model-registry sync-service
```

Stop containers and keep volumes:

```powershell
docker compose --env-file .env -f infrastructure\docker\docker-compose.yaml down
```

Stop containers and remove volumes:

```powershell
docker compose --env-file .env -f infrastructure\docker\docker-compose.yaml down -v
```

## Backend Smoke And Services

Run backend smoke test:

```powershell
uv run python scripts\smoke_backend.py
```

The smoke test is intentionally short-lived. It starts each service, checks `/health`, then stops it. Use `scripts\run_backend_local.ps1` or `uv run python scripts\smoke_backend.py --keep-alive` when you want the backend to remain available.

Check service health endpoints:

```powershell
curl.exe http://127.0.0.1:8000/health
curl.exe http://127.0.0.1:8001/health
curl.exe http://127.0.0.1:8002/health
curl.exe http://127.0.0.1:8003/health
curl.exe http://127.0.0.1:8004/health
curl.exe http://127.0.0.1:8005/health
curl.exe http://127.0.0.1:8006/health
```

API docs:

```text
API Gateway: http://127.0.0.1:8000/api/docs
Auth: http://127.0.0.1:8001/api/docs
AI: http://127.0.0.1:8002/docs
Analytics: http://127.0.0.1:8003/docs
Media: http://127.0.0.1:8004/api/docs
Model Registry: http://127.0.0.1:8005/api/docs
Sync: http://127.0.0.1:8006/api/docs
```

Run one service manually, example AI service:

```powershell
$env:PYTHONPATH="services\ai-service;shared\types;shared\inference-sdk;shared\utilities"
uv run --package ai-service uvicorn main:app --host 127.0.0.1 --port 8002 --app-dir services\ai-service
```

Run API Gateway manually:

```powershell
$env:PYTHONPATH="services\api-gateway;shared\types;shared\utilities"
uv run --package api-gateway uvicorn main:app --host 127.0.0.1 --port 8000 --app-dir services\api-gateway
```

## Migrations

List migration-aware services:

```powershell
uv run python scripts\migration.py list
```

Create all metadata-backed tables:

```powershell
uv run python scripts\migration.py create-tables --service all
```

Reset all metadata-backed tables:

```powershell
uv run python scripts\migration.py reset --service all --yes
```

Create model-registry Alembic revision:

```powershell
uv run python scripts\migration.py create --service model-registry -m "describe change" --autogenerate
```

Upgrade model-registry:

```powershell
uv run python scripts\migration.py upgrade --service model-registry
```

Downgrade model-registry to base:

```powershell
uv run python scripts\migration.py downgrade --service model-registry --revision base
```

Check current model-registry revision:

```powershell
uv run python scripts\migration.py current --service model-registry
```

Show migration history:

```powershell
uv run python scripts\migration.py history --service model-registry
```

## Model Promotion Checklist

Before promoting a model version:

1. Prepare dataset with versioned output.
2. Train checkpoint.
3. Export ONNX and quantized ONNX.
4. Evaluate on test split.
5. Inspect source metrics.
6. Inspect low-F1 classes in `classification_report.csv`.
7. Keep the full artifact package together.

Artifact package:

```text
models/plant-disease-v2/
  best_model.pth
  metadata.json
  plant_disease_mobilenetv3.onnx
  plant_disease_mobilenetv3.onnx.data
  plant_disease_mobilenetv3.quant.onnx
  plant_disease_mobilenetv3.export.json
  evaluation.json
  classification_report.csv
  confusion_matrix.csv
  source_metrics.csv
```

## Troubleshooting

CUDA requested but unavailable:

```powershell
uv run --package ai-service python scripts\training\check_torch.py
```

Install the CUDA PyTorch build:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\training\setup_torch.ps1 -Variant cu128
```

ONNX fixed batch rejects larger batches during evaluation:

```powershell
uv run --package ai-service python scripts\training\evaluate.py `
  --model_path models\plant-disease-v2\plant_disease_mobilenetv3.quant.onnx `
  --model_type onnx `
  --batch_size 1
```

Use PyTorch checkpoint evaluation for faster batched CPU/GPU evaluation:

```powershell
uv run --package ai-service python scripts\training\evaluate.py `
  --model_path models\plant-disease-v2\best_model.pth `
  --model_type torch `
  --batch_size 32
```

Port conflicts:

```text
8000-8006 backend services
15432 PostgreSQL
6380 Redis
9000 MinIO API
9001 MinIO Console
```

Broken `.venv`:

```powershell
uv venv --clear
uv sync --all-packages
```
