# Agriculture AI Platform — Claude Code Guide

## Project Overview

Hybrid AI-powered plant disease detection platform. Farmers capture plant images on mobile, get instant disease diagnoses with treatment recommendations, and work offline with automatic sync when connectivity returns.

**MVP targets:** Tomato, Cassava, Maize — ~15 diseases total  
**Inference model:** MobileNetV3 (edge + cloud via ONNX)  
**Backend status:** Fully scaffolded and containerized (7 services)  
**Frontend status:** Not yet built (`apps/` and `edge/` directories are empty placeholders)

---

## Repository Structure

```
agriculture-ai-platform/
├── services/                   # 7 FastAPI microservices (BUILT)
│   ├── api-gateway/            # Port 8000 — central router + auth middleware
│   ├── auth-service/           # Port 8001 — JWT, Argon2, sessions, 2FA, OAuth
│   ├── ai-service/             # Port 8002 — ONNX/PyTorch inference + Celery
│   ├── analytics-service/      # Port 8003 — aggregation, Pandas, Prometheus
│   ├── media-service/          # Port 8004 — image upload, MinIO/S3/R2
│   ├── model-registry/         # Port 8005 — MLflow, model versioning
│   └── sync-service/           # Port 8006 — offline-first sync queue
│
├── shared/                     # Shared Python packages (BUILT)
│   ├── types/                  # Pydantic schemas, SQLAlchemy models, enums
│   ├── inference-sdk/          # HybridInference engine (edge/cloud/hybrid)
│   └── utilities/              # image_utils, geometry_utils, validators
│
├── infrastructure/
│   ├── docker/                 # docker-compose.yaml + all Dockerfiles (BUILT)
│   │   ├── docker-compose.yaml
│   │   ├── Dockerfile.api-gateway
│   │   ├── Dockerfile.ai-service
│   │   ├── Dockerfile.model-registry
│   │   ├── Dockerfile.sync-service
│   │   ├── init-db.sql         # seeds schemas, indexes, materialized view
│   │   ├── prometheus.yml
│   │   └── nginx/nginx.conf
│   └── kubernetes/             # EMPTY — not yet implemented
│
├── apps/                       # EMPTY — Flutter (mobile) + Next.js (web) planned
│   ├── mobile/
│   └── web/
│
├── edge/                       # EMPTY — ONNX mobile runtime, drone SDK planned
│   ├── mobile-inference/
│   ├── edge-runtime/
│   └── drone-sdk/
│
├── scripts/
│   ├── deployment/             # deploy.sh, setup-ssl.sh, setup-monitoring.sh
│   ├── migration/              # DB migration helpers
│   └── training/               # train.py, export_onnx.py, quantize.py
│
├── datasets/                   # raw/, processed/, augmented/ (currently empty)
├── docs/                       # EMPTY — documentation planned
├── pyproject.toml              # uv workspace root (10 members)
├── uv.lock                     # pinned dependency lockfile
├── .env.example                # all 55 required env vars documented
└── .python-version             # 3.13
```

---

## Tech Stack

| Layer | Technology | Notes |
|---|---|---|
| Language | Python 3.13 | enforced by `.python-version` |
| Package manager | uv | workspace monorepo |
| Web framework | FastAPI 0.136.3+ | all 7 services |
| ASGI server | Uvicorn 0.48.0+ | with standard extras |
| Database | PostgreSQL 15 | 3 schemas: agriculture, analytics, telemetry |
| ORM | SQLAlchemy 2.0+ | async with asyncpg |
| Migrations | Alembic 1.18.4+ | auth-service is the only service with migrations wired up |
| Cache / broker | Redis 7 | sessions, rate limits, Celery broker |
| Object storage | MinIO (dev) / S3 / Cloudflare R2 (prod) | abstracted behind `STORAGE_TYPE` env var |
| ML training | PyTorch 2.10.0+ / TorchVision | |
| Model format | ONNX 1.21.0+ | exported from PyTorch for edge deployment |
| Inference | ONNX Runtime 1.26.0+ | CPU; CUDA optional via `USE_GPU=true` |
| Computer vision | OpenCV 4.13+ / Pillow 12.2+ | |
| Data analysis | Pandas 3.0.3+ / NumPy 2.4.6+ | analytics-service |
| Task queue | Celery 5.6.3+ | ai-service, media-service, sync-service |
| Auth | python-jose (JWT) + passlib[argon2] | Argon2 password hashing |
| Rate limiting | slowapi 0.1.9+ | applied in api-gateway |
| Model tracking | MLflow 1.27+ | model-registry only |
| Monitoring | Prometheus + Grafana | all services instrumented |
| Reverse proxy | Nginx | TLSv1.2/1.3, gzip, HTTP/2 |
| Containers | Docker + Docker Compose 3.8 | 13-service stack |

---

## Development Setup

### Prerequisites
- Python 3.13 (use `pyenv` or install directly)
- [uv](https://docs.astral.sh/uv/) package manager
- Docker + Docker Compose

### First-time setup
```bash
# Install all workspace dependencies
uv sync

# Copy and fill environment variables
cp .env.example .env
# Edit .env — at minimum set SECRET_KEY, DB_PASSWORD, REDIS_PASSWORD, MINIO_ROOT_USER, MINIO_ROOT_PASSWORD

# Start the full stack
docker compose -f infrastructure/docker/docker-compose.yaml up -d

# Run database migrations (auth-service)
docker compose -f infrastructure/docker/docker-compose.yaml exec auth-service alembic upgrade head
```

### Running a single service locally (without Docker)
```bash
# From the service directory — uv runs in the workspace context
cd services/api-gateway
uv run python main.py

# Or from repo root
uv run --package api-gateway python services/api-gateway/main.py
```

---

## Service Map

| Service | Port | Entry point | Config | Key files |
|---|---|---|---|---|
| api-gateway | 8000 | `services/api-gateway/main.py` | `app/config.py` | `app/api/v1/`, `app/clients/`, `app/middleware/` |
| auth-service | 8001 | `services/auth-service/main.py` | `app/config.py` | `app/api/v1/auth.py`, `app/models/user.py`, `app/core/security.py` |
| ai-service | 8002 | `services/ai-service/main.py` | `app/config.py` | `app/core/inference_engine.py`, `app/core/model_registry.py`, `app/worker.py` |
| analytics-service | 8003 | `services/analytics-service/main.py` | `app/config.py` | `app/services/analytics_engine.py`, `app/scheduler.py` |
| media-service | 8004 | `services/media-service/main.py` | `app/config.py` | `app/core/storage.py`, `app/core/image_processor.py` |
| model-registry | 8005 | `services/model-registry/main.py` | `app/config.py` | `app/core/registry.py`, `app/core/model_manager.py` |
| sync-service | 8006 | `services/sync-service/main.py` | `app/config.py` | `app/core/sync_engine.py`, `app/core/conflict_resolver.py` |

### API Gateway public paths (no JWT required)
```
/health  /ready  /metrics  /api/docs  /api/redoc  /api/openapi.json
/api/v1/auth/register  /api/v1/auth/login  /api/v1/auth/refresh
/api/v1/auth/forgot-password  /api/v1/auth/reset-password
/api/v1/auth/verify-email  /api/v1/auth/resend-verification
```

### Key prediction endpoints (through api-gateway)
```
POST /api/v1/predict/single          # single image — 10 req/min
POST /api/v1/predict/batch           # batch images — 5 req/min
POST /api/v1/predict/upload-image    # multipart upload + predict — 20 req/min
GET  /api/v1/predict/history/{user_id}
```

---

## Shared Libraries

Import these in services — never duplicate the logic.

### `shared/types` → package `agriculture-ai-shared`
```python
from agriculture_ai.types.enums import CropType, DiseaseType, DeviceType, UserRole, InferenceSource, ModelType, PredictionStatus
from agriculture_ai.types.schemas import UserCreate, UserResponse, PredictionRequest, PredictionResponse, SyncRequest
from agriculture_ai.types.models import User, Farm, Scan, Prediction, Device, ModelVersion, SyncLog
```
- **CropType:** TOMATO, CASSAVA, MAIZE
- **DiseaseType:** 18 variants (7 tomato, 4 cassava, 4 maize, others)
- **DeviceType:** MOBILE, WEB, DRONE, UAV, JETSON, RASPBERRY_PI, IOT_SENSOR
- **UserRole:** FARMER, AGRONOMIST, ADMIN, RESEARCHER

### `shared/inference-sdk` → package `agriculture-inference-sdk`
```python
from agriculture_inference.hybrid_inference import HybridInference
from agriculture_inference.inference_engine import InferenceEngine
from agriculture_inference.preprocessing import preprocess_image
```
- `HybridInference` — modes: `EDGE_ONLY`, `CLOUD_ONLY`, `HYBRID`, `FALLBACK`
- Edge-first, cloud verification if confidence < 0.7 (configurable)
- Queues predictions when offline; syncs in background

### `shared/utilities` → package `agriculture-utilities`
```python
from agriculture_utils.image_utils import resize_image, convert_format
from agriculture_utils.validators import validate_image_file
from agriculture_utils.geometry_utils import haversine_distance
from agriculture_utils.datetime_utils import to_utc, localize_timestamp
from agriculture_utils.postprocessing import format_prediction_result
```

---

## Common Commands

### uv (package management)
```bash
uv sync                                          # sync all workspace deps
uv add <package> --package <service-name>        # add dep to specific service
uv run python <script>                           # run in workspace venv
uv pip install -e shared/types                   # editable install of shared lib
```

### Docker Compose
```bash
# Start full stack
docker compose -f infrastructure/docker/docker-compose.yaml up -d

# Start specific services
docker compose -f infrastructure/docker/docker-compose.yaml up -d postgres redis minio

# View logs
docker compose -f infrastructure/docker/docker-compose.yaml logs -f api-gateway

# Rebuild a service after code changes
docker compose -f infrastructure/docker/docker-compose.yaml up -d --build api-gateway

# Tear down (keep volumes)
docker compose -f infrastructure/docker/docker-compose.yaml down

# Tear down + wipe data
docker compose -f infrastructure/docker/docker-compose.yaml down -v
```

### Database migrations (Alembic — auth-service)
```bash
cd services/auth-service

# Create a new migration
uv run alembic revision --autogenerate -m "describe the change"

# Apply migrations
uv run alembic upgrade head

# Rollback one step
uv run alembic downgrade -1
```

### Celery workers
```bash
# ai-service worker
cd services/ai-service
uv run celery -A app.worker worker --loglevel=info

# media-service thumbnail worker
cd services/media-service
uv run celery -A app.workers.thumbnail_worker worker --loglevel=info

# sync-service worker
cd services/sync-service
uv run celery -A app.workers.sync_worker worker --loglevel=info
```

### AI training & export
```bash
# Train model
uv run python scripts/training/train.py --model mobilenetv3 --epochs 50

# Export to ONNX
uv run python scripts/training/export_onnx.py --checkpoint path/to/model.pth

# Quantize ONNX model for edge
uv run python scripts/training/quantize.py --input model.onnx --output model_quantized.onnx

# Prepare dataset splits
uv run python scripts/training/prepare_dataset.py
uv run python scripts/training/split_dataset.py
```

### Deployment
```bash
# Full automated deploy
bash scripts/deployment/deploy.sh production

# SSL setup (run once on a new server)
bash scripts/deployment/setup-ssl.sh

# Monitoring setup
bash scripts/deployment/setup-monitoring.sh
```

---

## Architecture Patterns

Follow these patterns in all services — they are already established across the codebase.

### Service config (pydantic-settings)
Every service has `app/config.py`:
```python
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    secret_key: str
    database_url: str
    redis_url: str = "redis://localhost:6379"
    debug: bool = False

    class Config:
        env_file = ".env"

settings = Settings()
```

### Health + readiness endpoints
Every service must expose both:
```python
@app.get("/health")
async def health():
    return {"status": "healthy", "service": "my-service"}

@app.get("/ready")
async def ready():
    # check DB + Redis connectivity
    return {"status": "ready"}
```

### Prometheus instrumentation
```python
from prometheus_fastapi_instrumentator import Instrumentator
Instrumentator().instrument(app).expose(app)
```

### Async database access
All DB operations use SQLAlchemy 2.0 async style with asyncpg:
```python
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

engine = create_async_engine(settings.database_url, echo=settings.debug)
AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

async def get_db():
    async with AsyncSessionLocal() as session:
        yield session
```

### Service-to-service communication
All inter-service calls go through the clients in `services/api-gateway/app/clients/`. Never call downstream services directly from other services — route through the gateway or use the client pattern.

### Storage abstraction
Media and model-registry services use `STORAGE_TYPE` env var to switch backends:
```
STORAGE_TYPE=minio    # local dev
STORAGE_TYPE=s3       # AWS
STORAGE_TYPE=r2       # Cloudflare R2
STORAGE_TYPE=local    # filesystem fallback
```

### Inference modes
Use `InferenceSource` enum from shared types when recording predictions:
- `EDGE` — local ONNX on device
- `CLOUD` — backend PyTorch/ONNX inference
- `HYBRID` — edge first, cloud verification

---

## Environment Variables

Copy `.env.example` to `.env`. Key groups:

```bash
# Security (required everywhere — min 32 chars)
SECRET_KEY=

# Database
DB_PASSWORD=
DATABASE_URL=postgresql+asyncpg://agri_user:${DB_PASSWORD}@localhost:5432/agriculture_ai

# Redis
REDIS_PASSWORD=
REDIS_URL=redis://:${REDIS_PASSWORD}@localhost:6379

# Object storage (dev uses MinIO)
MINIO_ROOT_USER=
MINIO_ROOT_PASSWORD=
STORAGE_TYPE=minio
STORAGE_ENDPOINT=localhost:9000
STORAGE_BUCKET=agriculture-images

# AI model
MODEL_PATH=/models/mobilenetv3_best.pth
USE_GPU=false
NUM_CLASSES=15

# Service URLs (used by api-gateway clients)
AUTH_SERVICE_URL=http://auth-service:8001
AI_SERVICE_URL=http://ai-service:8002
ANALYTICS_SERVICE_URL=http://analytics-service:8003
MEDIA_SERVICE_URL=http://media-service:8004
MODEL_REGISTRY_URL=http://model-registry:8005
SYNC_SERVICE_URL=http://sync-service:8006

# Auth service extras
SMTP_HOST=
SMTP_PORT=587
SMTP_USER=
SMTP_PASSWORD=

# Monitoring
GRAFANA_PASSWORD=
PROMETHEUS_MULTIPROC_DIR=/tmp/prometheus

# Application
DEBUG=false
ENVIRONMENT=production
LOG_LEVEL=INFO
CORS_ORIGINS=http://localhost:3000,http://localhost:8080
```

---

## Monitoring & Observability

| Tool | URL | Purpose |
|---|---|---|
| API Docs | http://localhost:8000/api/docs | OpenAPI for all gateway routes |
| Grafana | http://localhost:3000 | Dashboards (admin / `GRAFANA_PASSWORD`) |
| Prometheus | http://localhost:9090 | Raw metrics |
| MinIO Console | http://localhost:9001 | Object storage browser |
| Individual service docs | http://localhost:800X/docs | Each service has its own OpenAPI |

Prometheus scrapes every service at `/metrics` every 15s. Grafana is pre-configured to connect to Prometheus.

---

## What Is Not Built Yet

Do not create files in these directories — they are empty placeholders for future phases:

- `apps/mobile/` — Flutter app (offline-first, ONNX Runtime Mobile, Riverpod)
- `apps/web/` — Next.js admin dashboard (TypeScript, TailwindCSS)
- `edge/mobile-inference/` — compiled ONNX mobile runner
- `edge/edge-runtime/` — Jetson / Raspberry Pi runtime
- `edge/drone-sdk/` — MAVLink, UAV telemetry
- `infrastructure/kubernetes/` — K8s manifests
- `docs/` — architecture diagrams, API docs, deployment guides
- `.github/workflows/` — CI/CD pipelines (GitHub Actions)

---

## Engineering Rules

From the project spec — apply these in all new code:

**Never:**
- Tightly couple frontend and AI logic
- Hardcode inference mode (cloud-only or edge-only)
- Build monolithic backend logic into a single service
- Add models or schemas outside of `shared/types` unless they are service-private

**Always:**
- Use `HybridInference` from `shared/inference-sdk` for any inference logic
- Export models to ONNX — PyTorch checkpoints are for training only
- Import shared enums/schemas from `agriculture_ai.types` — do not redefine them
- Use async/await throughout (FastAPI + asyncpg + asyncio)
- Add `/health` and `/ready` to every new service
- Instrument every new service with Prometheus via `prometheus-fastapi-instrumentator`
- Keep APIs versioned under `/api/v1/`
- Validate all external input with Pydantic schemas
- Hash passwords with Argon2 (passlib) — never store plaintext or use bcrypt
- Use `pydantic-settings` for all configuration — no bare `os.getenv()`

---

## Database Schemas

PostgreSQL has 3 schemas (created by `init-db.sql`):

| Schema | Tables | Purpose |
|---|---|---|
| `agriculture` | users, farms, scans, predictions, diseases, treatments, devices, model_versions, sync_logs | Core application data |
| `analytics` | aggregated metrics, daily_metrics (materialized view) | Analytics aggregation |
| `telemetry` | telemetry records (GPS, sensor, status, detection events) | UAV/IoT telemetry (future) |

Alembic migration scripts live in `services/auth-service/alembic/`. When adding tables, create migrations there and apply them — do not manually ALTER the database.
