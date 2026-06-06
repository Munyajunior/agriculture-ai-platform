# Backend Documentation

This guide explains the completed backend of the Agriculture AI Platform in plain language. It is written for both engineers and non-engineers: first it explains what each piece does, then it gives the exact commands needed to run, test, and maintain the backend.

## Documentation Map

Use these backend docs together:

| Document | Use |
| --- | --- |
| [Backend Documentation](README.md) | Start here for the backend overview and common workflows. |
| [Backend API Reference](API.md) | Route map, base URLs, auth behavior, and API usage notes. |
| [Backend Architecture](ARCHITECTURE.md) | Service boundaries, data ownership, runtime flow, and shared-code policy. |
| [Backend Deployment Guide](DEPLOYMENT.md) | Local/Compose deployment, ports, volumes, migrations, verification, and promotion checklist. |
| [Backend Service Reference](SERVICE_REFERENCE.md) | File-by-file service map and implementation reference. |

## What The Backend Does

The backend is a group of FastAPI services. Each service owns a focused part of the platform:

| Service | Port | Purpose |
| --- | ---: | --- |
| API Gateway | 8000 | Public entry point that forwards client calls to internal services. |
| Auth Service | 8001 | User registration, login, JWT tokens, sessions, OAuth, API keys. |
| AI Service | 8002 | Plant disease prediction and model loading for inference. |
| Analytics Service | 8003 | Dashboards, disease trends, reports, alerts, metrics. |
| Media Service | 8004 | Image upload, chunked upload, download, thumbnails, MinIO storage. |
| Model Registry | 8005 | Model version metadata, deployment records, model metrics. |
| Sync Service | 8006 | Offline sync queue, device registration, conflict handling. |

The backend also uses shared packages:

| Package | Path | Purpose |
| --- | --- | --- |
| Shared Types | `shared/types` | Shared SQLAlchemy models, enums, and Pydantic schemas. |
| Inference SDK | `shared/inference-sdk` | Reusable inference, preprocessing, and model helper code. |
| Utilities | `shared/utilities` | Common helpers for async, datetime, geometry, images, HTTP, logging, validation, and postprocessing. |

## Local Infrastructure

The local backend depends on:

| Dependency | Container | Host URL |
| --- | --- | --- |
| PostgreSQL | `agri_postgres` | `127.0.0.1:15432` |
| Redis | `agri_redis` | `127.0.0.1:6380` |
| MinIO API | `agri_minio` | `http://localhost:9000` |
| MinIO Console | `agri_minio` | `http://localhost:9001` |

PostgreSQL and Redis use non-default host ports to avoid clashing with other local databases/caches.

Default local credentials are stored in `.env` and each service `.env`. These files are intentionally ignored by git so local secrets can be changed without being committed.

## Prerequisites

Install:

- Docker Desktop or Docker Engine with Docker Compose
- Python 3.13
- `uv`
- PowerShell on Windows

The current local workflow has been verified on Windows PowerShell.

## First Run

From the repository root:

```powershell
uv sync --all-packages
powershell -ExecutionPolicy Bypass -File scripts\setup_infrastructure.ps1
uv run python scripts\smoke_backend.py
```

Expected smoke result:

```text
## api-gateway: stayed up and passed /health
## auth-service: stayed up and passed /health
## ai-service: stayed up and passed /health
## analytics-service: stayed up and passed /health
## media-service: stayed up and passed /health
## model-registry: stayed up and passed /health
## sync-service: stayed up and passed /health
```

## One Command Local Check

This command starts required infrastructure and runs the backend smoke test:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\run_backend_local.ps1
```

It is the easiest command for a new developer to confirm the backend is usable.

## Environment Files

There are two levels of environment files.

Root `.env`:

```text
DB_PASSWORD=secure_password
REDIS_PASSWORD=redis_pass
MINIO_ROOT_USER=minioadmin
MINIO_ROOT_PASSWORD=minioadmin123
SECRET_KEY=abcdefghijklmnopqrstuvwxyz1234567890
GRAFANA_PASSWORD=admin
USE_GPU=false
```

Each service also has its own `.env` under `services/<service-name>/.env`.

Local direct service runs use:

- PostgreSQL at `127.0.0.1:15432`
- Redis at `127.0.0.1:6380`
- MinIO at `localhost:9000`

Docker Compose overrides those URLs inside containers:

- PostgreSQL at `postgres:5432`
- Redis at `redis:6379`
- MinIO at `minio:9000`

## Docker Compose

Compose file:

```text
infrastructure/docker/docker-compose.yaml
```

Validate compose config:

```powershell
docker compose --env-file .env -f infrastructure\docker\docker-compose.yaml config --quiet
```

Start infrastructure:

```powershell
docker compose --env-file .env -f infrastructure\docker\docker-compose.yaml up -d postgres redis minio
```

Start backend services with compose:

```powershell
docker compose --env-file .env -f infrastructure\docker\docker-compose.yaml up -d api-gateway auth-service ai-service analytics-service media-service model-registry sync-service
```

Build and start backend services:

```powershell
docker compose --env-file .env -f infrastructure\docker\docker-compose.yaml up -d --build api-gateway auth-service ai-service analytics-service media-service model-registry sync-service
```

## Infrastructure Setup Script

Script:

```text
scripts/setup_infrastructure.ps1
```

What it does:

- Starts or creates PostgreSQL, Redis, and MinIO containers.
- Waits for each container to become healthy.
- Ensures the PostgreSQL `agri_user` password matches `.env`.
- Creates MinIO buckets:
  - `agriculture-images`
  - `ai-models`
  - `models`
- Optionally starts backend services.

Commands:

```powershell
# Start only PostgreSQL, Redis, MinIO
powershell -ExecutionPolicy Bypass -File scripts\setup_infrastructure.ps1

# Reset compose volumes, then start infrastructure
powershell -ExecutionPolicy Bypass -File scripts\setup_infrastructure.ps1 -ResetVolumes

# Start infrastructure and backend service containers
powershell -ExecutionPolicy Bypass -File scripts\setup_infrastructure.ps1 -Services

# Build backend images, then start services
powershell -ExecutionPolicy Bypass -File scripts\setup_infrastructure.ps1 -Services -Build
```

Use `-ResetVolumes` only when it is acceptable to destroy local database/cache/object-storage data.

## Smoke Test Script

Script:

```text
scripts/smoke_backend.py
```

What it does:

- Starts each backend service with `uvicorn`.
- Loads that service's `.env`.
- Sets service-specific `PYTHONPATH`.
- Waits up to 90 seconds for `/health`.
- Terminates the service after the check.
- Reports service output if startup fails.

Run:

```powershell
uv run python scripts\smoke_backend.py
```

This script is the best quick confidence check after changing backend code.

## Migration Script

Script:

```text
scripts/migration.py
```

What it does:

- Lists services that expose SQLAlchemy metadata.
- Creates/drops/resets tables using SQLAlchemy metadata.
- Initializes Alembic for services.
- Creates Alembic revisions.
- Runs Alembic upgrade/downgrade/current/history/heads/stamp.
- Filters Alembic autogenerate to service-owned tables so one service does not try to drop another service's tables in the shared database.

List services:

```powershell
uv run python scripts\migration.py list
```

Current result:

```text
ai              metadata=yes alembic=no
analytics       metadata=no  alembic=no
auth            metadata=yes alembic=no
media           metadata=yes alembic=no
model-registry  metadata=yes alembic=yes
sync            metadata=yes alembic=no
```

Create tables for one service:

```powershell
uv run python scripts\migration.py create-tables --service media
```

Drop tables for one service:

```powershell
uv run python scripts\migration.py drop --service media --yes
```

Reset all metadata-backed services:

```powershell
uv run python scripts\migration.py reset --service all --yes
```

`analytics` is skipped during `--service all` metadata operations because it does not currently expose SQLAlchemy metadata.

Initialize Alembic for model-registry:

```powershell
uv run python scripts\migration.py init --service model-registry
```

Create a revision:

```powershell
uv run python scripts\migration.py create --service model-registry -m "baseline model registry" --autogenerate
```

Upgrade:

```powershell
uv run python scripts\migration.py upgrade --service model-registry
```

Downgrade:

```powershell
uv run python scripts\migration.py downgrade --service model-registry --revision base
```

Check current revision:

```powershell
uv run python scripts\migration.py current --service model-registry
```

Current model-registry baseline:

```text
10d82dd979df (head)
```

## Health And Readiness

Every backend service exposes:

```text
GET /health
GET /ready
```

Service docs are available through FastAPI when a service is running:

| Service | Docs URL |
| --- | --- |
| API Gateway | `http://127.0.0.1:8000/api/docs` |
| Auth Service | `http://127.0.0.1:8001/api/docs` |
| AI Service | `http://127.0.0.1:8002/docs` |
| Analytics Service | `http://127.0.0.1:8003/docs` |
| Media Service | `http://127.0.0.1:8004/api/docs` |
| Model Registry | `http://127.0.0.1:8005/api/docs` |
| Sync Service | `http://127.0.0.1:8006/api/docs` |

## Service Communication

Clients should normally call the API Gateway. The API Gateway forwards to internal services through typed HTTP clients under:

```text
services/api-gateway/app/clients
```

Direct service calls are useful for development and debugging.

Local gateway service URLs:

```text
AUTH_SERVICE_URL=http://localhost:8001
AI_SERVICE_URL=http://localhost:8002
ANALYTICS_SERVICE_URL=http://localhost:8003
MEDIA_SERVICE_URL=http://localhost:8004
MODEL_REGISTRY_URL=http://localhost:8005
SYNC_SERVICE_URL=http://localhost:8006
```

Docker service URLs:

```text
AUTH_SERVICE_URL=http://auth-service:8001
AI_SERVICE_URL=http://ai-service:8002
ANALYTICS_SERVICE_URL=http://analytics-service:8003
MEDIA_SERVICE_URL=http://media-service:8004
MODEL_REGISTRY_URL=http://model-registry:8005
SYNC_SERVICE_URL=http://sync-service:8006
```

## Backend Services

### API Gateway

Path:

```text
services/api-gateway
```

Purpose:

- Public backend entry point.
- Validates and forwards requests to internal services.
- Applies request logging, authentication middleware, CORS, and rate limiting.
- Hosts gateway-level schemas for client-facing request/response shapes.

Main routes:

```text
/api/v1/auth
/api/v1/predict
/api/v1/analytics
/api/v1/sync
/api/v1/devices
/api/v1/models
```

Use the gateway when building frontend/mobile clients unless debugging a specific internal service.

### Auth Service

Path:

```text
services/auth-service
```

Purpose:

- User registration and login.
- JWT access/refresh token flow.
- Password reset and email verification workflows.
- OAuth account linking.
- API key management.
- Session management and admin session inspection.

Main routes:

```text
/api/v1/auth
/api/v1/users
/api/v1/oauth
/api/v1/api-keys
/api/v1/sessions
```

Primary tables:

- Shared `users` table from `shared/types`.
- `api_keys`
- `oauth_accounts`
- `password_resets`
- `sessions`

### AI Service

Path:

```text
services/ai-service
```

Purpose:

- Loads an active/default model for plant disease inference.
- Provides single, batch, and image-upload prediction endpoints.
- Tracks available/active models from the model registry.
- Uses PyTorch model loading locally and supports ONNX configuration.

Main routes:

```text
/api/v1/predict
/api/v1/models
/api/v1/health
```

Important behavior:

- If model-registry is not running during AI startup, AI service falls back to a default local model configuration.
- A random/untrained default PyTorch model can load for development health checks.
- Production inference requires real model artifact configuration.

### Analytics Service

Path:

```text
services/analytics-service
```

Purpose:

- Dashboard summaries and time series.
- Disease statistics and trends.
- Reports and exports.
- Alert rules and notifications.
- Background scheduled jobs.
- Predictive analytics placeholders and services.

Main routes:

```text
/api/v1/dashboard
/api/v1/diseases
/api/v1/analytics
/api/v1/reports
/api/v1/alerts
```

Current database note:

- Analytics currently initializes DB connectivity but does not expose service-local SQLAlchemy metadata for `scripts/migration.py`.

### Media Service

Path:

```text
services/media-service
```

Purpose:

- Image upload.
- Chunked upload.
- Image download.
- Thumbnail download.
- MinIO/S3-compatible storage.
- Local storage fallback.
- Redis-backed cache.
- Thumbnail worker.

Main routes:

```text
/api/v1/upload
/api/v1/download
```

Primary tables:

- `media_files`
- `upload_sessions`
- `image_analysis`

Storage:

- Default local setup uses MinIO.
- Buckets are created by `scripts/setup_infrastructure.ps1`.
- Storage code uses `boto3` wrapped in async helpers so FastAPI is not blocked by S3 calls.

### Model Registry

Path:

```text
services/model-registry
```

Purpose:

- Register model versions.
- Store model artifact paths.
- Track active/production models.
- Record deployments.
- Record metrics.
- Compare model performance.
- Provide download URLs for model artifacts.

Main routes:

```text
/api/v1/models
/api/v1/deployments
/api/v1/metrics
```

Primary tables:

- `model_versions`
- `model_deployments`
- `model_metrics`
- `model_experiments`

Migration status:

- Alembic is initialized for this service.
- Current baseline revision is `10d82dd979df`.

### Sync Service

Path:

```text
services/sync-service
```

Purpose:

- Offline-first synchronization.
- Device registration and heartbeat.
- Sync queue management.
- Conflict detection and resolution.
- Sync worker startup.

Main routes:

```text
/api/v1/sync
/api/v1/devices
/api/v1/conflicts
```

Primary tables:

- `sync_queue`
- `sync_logs`
- `sync_conflicts`
- `device_sync_state`

## Shared Database Model Groups

Shared platform models live in:

```text
shared/types/agriculture_ai/types/models.py
```

Important shared tables:

- `users`
- `farms`
- `scans`
- `predictions`
- `diseases`
- `treatments`
- `devices`
- `telemetry`
- shared `model_versions`
- shared `sync_logs`

Some services also own service-local tables. The migration script is aware of which service metadata to use.

## Shared Schemas And Enums

Shared Pydantic schemas:

```text
shared/types/agriculture_ai/types/schemas.py
```

Shared enums:

```text
shared/types/agriculture_ai/types/enums.py
```

These provide common request/response and enum types for user, prediction, sync, device, analytics, crop, disease, inference, role, treatment, telemetry, and model workflows.

## Common Developer Workflows

### Verify backend from scratch

```powershell
uv sync --all-packages
powershell -ExecutionPolicy Bypass -File scripts\setup_infrastructure.ps1
uv run python scripts\migration.py reset --service all --yes
uv run python scripts\smoke_backend.py
```

### Add a model-registry schema change

1. Edit SQLAlchemy models in `services/model-registry/app/database.py`.
2. Generate migration:

```powershell
uv run python scripts\migration.py create --service model-registry -m "describe change" --autogenerate
```

3. Review generated file in:

```text
services/model-registry/migrations/versions
```

4. Apply migration:

```powershell
uv run python scripts\migration.py upgrade --service model-registry
```

5. Run smoke test:

```powershell
uv run python scripts\smoke_backend.py
```

### Reset local backend database

This destroys local backend tables:

```powershell
uv run python scripts\migration.py reset --service all --yes
```

Use only for local/dev data or intentionally disposable environments.

## Troubleshooting

### PostgreSQL password errors

Run:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\setup_infrastructure.ps1
```

The script repairs the local `agri_user` password to match `.env`.

### Port conflicts

Expected host ports:

```text
15432 PostgreSQL
6380 Redis
9000  MinIO API
9001  MinIO Console
8000-8006 backend services
```

If another service uses one of these ports, stop it or update the related `.env`/compose port mapping.

### Broken virtual environment

If `uv` reports that `.venv` is broken:

```powershell
uv venv --clear
uv sync --all-packages
```

### Alembic autogenerate tries to drop other services' tables

Do not apply that migration. The generated Alembic env includes service-owned table filtering. Re-run:

```powershell
uv run python scripts\migration.py init --service <service>
uv run python scripts\migration.py create --service <service> -m "message" --autogenerate
```

Then review the generated revision before upgrading.

## Current Limitations

- Analytics has no service-local SQLAlchemy metadata wired into the migration script yet.
- Model-registry is the only service with Alembic initialized right now.
- AI service can pass health with the development default model, but real production inference requires real model artifacts.
- Frontend, mobile, production, and edge deployment docs are intentionally out of scope for this backend documentation pass.
