# Backend Deployment Guide

This guide explains how to run the completed backend locally and with Docker Compose. It also lists the steps needed before promoting the backend to a real staging or production environment.

## Deployment Status

The verified deployment target today is local development:

- PostgreSQL, Redis, and MinIO run in Docker.
- Backend services can run directly through the smoke script.
- Backend services can also be built and started through Docker Compose.
- Model-registry Alembic migrations are initialized and tested.

Production deployment is not fully hardened yet. Use the production checklist near the end of this document before exposing the system outside a development environment.

## Prerequisites

Install:

- Docker Desktop or Docker Engine with Docker Compose
- Python 3.13
- `uv`
- PowerShell on Windows

From the repository root, install Python dependencies:

```powershell
uv sync --all-packages
```

## Environment Files

The deployment reads two levels of environment files:

| File | Purpose |
| --- | --- |
| `.env` | Root infrastructure values shared by Compose. |
| `services/<service>/.env` | Service-specific application settings. |

The files are intentionally ignored by git. Keep real secrets out of committed files.

Default local infrastructure values:

```text
DB_PASSWORD=secure_password
REDIS_PASSWORD=redis_pass
MINIO_ROOT_USER=minioadmin
MINIO_ROOT_PASSWORD=minioadmin123
SECRET_KEY=abcdefghijklmnopqrstuvwxyz1234567890
GRAFANA_PASSWORD=admin
USE_GPU=false
```

Change these before any shared staging or production deployment.

## Local Development Deployment

Start infrastructure:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\setup_infrastructure.ps1
```

Run the backend smoke test:

```powershell
uv run python scripts\smoke_backend.py
```

Or run both with one command:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\run_backend_local.ps1
```

The smoke script starts each service, waits for `/health`, reports success or failure, and shuts the service down before moving to the next one.

## Docker Compose Deployment

Compose file:

```text
infrastructure/docker/docker-compose.yaml
```

Validate Compose configuration:

```powershell
docker compose --env-file .env -f infrastructure\docker\docker-compose.yaml config --quiet
```

Start only infrastructure:

```powershell
docker compose --env-file .env -f infrastructure\docker\docker-compose.yaml up -d postgres redis minio
```

Build and start backend services:

```powershell
docker compose --env-file .env -f infrastructure\docker\docker-compose.yaml up -d --build api-gateway auth-service ai-service analytics-service media-service model-registry sync-service
```

Start observability and proxy services when needed:

```powershell
docker compose --env-file .env -f infrastructure\docker\docker-compose.yaml up -d nginx prometheus grafana
```

## Service Ports

| Service | Host Port | Container Port |
| --- | ---: | ---: |
| API Gateway | 8000 | 8000 |
| Auth Service | 8001 | 8001 |
| AI Service | 8002 | 8002 |
| Analytics Service | 8003 | 8003 |
| Media Service | 8004 | 8004 |
| Model Registry | 8005 | 8005 |
| Sync Service | 8006 | 8006 |
| PostgreSQL | 15432 | 5432 |
| Redis | 6380 | 6379 |
| MinIO API | 9000 | 9000 |
| MinIO Console | 9001 | 9001 |
| Nginx | 80, 443 | 80, 443 |
| Prometheus | 9090 | 9090 |
| Grafana | 3000 | 3000 |

## Container Names

| Container | Purpose |
| --- | --- |
| `agri_postgres` | PostgreSQL database. |
| `agri_redis` | Redis cache/queue. |
| `agri_minio` | MinIO object storage. |
| `agri_api_gateway` | Public backend gateway. |
| `agri_auth_service` | Authentication service. |
| `agri_ai_service` | AI inference service. |
| `agri_analytics_service` | Analytics service. |
| `agri_media_service` | Media service. |
| `agri_model_registry` | Model registry service. |
| `agri_sync_service` | Sync service. |
| `agri_nginx` | Reverse proxy. |
| `agri_prometheus` | Metrics store. |
| `agri_grafana` | Dashboard UI. |

## Persistent Volumes

Compose creates these named volumes:

| Volume | Stores |
| --- | --- |
| `postgres_data` | PostgreSQL data. |
| `redis_data` | Redis data. |
| `minio_data` | MinIO object data. |
| `model_cache` | AI service model cache. |
| `model_registry` | Model registry model storage/cache. |
| `prometheus_data` | Prometheus data. |
| `grafana_data` | Grafana data. |

To reset local development data:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\setup_infrastructure.ps1 -ResetVolumes
```

Use this only when local data is disposable.

## Database Setup And Migrations

List migration-aware services:

```powershell
uv run python scripts\migration.py list
```

Create all metadata-backed service tables:

```powershell
uv run python scripts\migration.py create-tables --service all
```

Reset all metadata-backed service tables:

```powershell
uv run python scripts\migration.py reset --service all --yes
```

Upgrade model-registry through Alembic:

```powershell
uv run python scripts\migration.py upgrade --service model-registry
```

Check current model-registry revision:

```powershell
uv run python scripts\migration.py current --service model-registry
```

Current baseline:

```text
10d82dd979df
```

## Storage Setup

The setup script creates local MinIO buckets:

```text
agriculture-images
ai-models
models
```

MinIO local URLs:

| Interface | URL |
| --- | --- |
| API | `http://localhost:9000` |
| Console | `http://localhost:9001` |

Default local credentials are `minioadmin` / `minioadmin123` unless changed in `.env`.

## Verification

Check running containers:

```powershell
docker ps
```

Run backend smoke:

```powershell
uv run python scripts\smoke_backend.py
```

Check a service directly:

```powershell
curl.exe http://127.0.0.1:8000/health
curl.exe http://127.0.0.1:8001/health
curl.exe http://127.0.0.1:8002/health
curl.exe http://127.0.0.1:8003/health
curl.exe http://127.0.0.1:8004/health
curl.exe http://127.0.0.1:8005/health
curl.exe http://127.0.0.1:8006/health
```

## Logs

Show logs for one service:

```powershell
docker logs agri_api_gateway
```

Follow logs:

```powershell
docker logs -f agri_api_gateway
```

Compose logs for all backend services:

```powershell
docker compose --env-file .env -f infrastructure\docker\docker-compose.yaml logs -f api-gateway auth-service ai-service analytics-service media-service model-registry sync-service
```

## Stop And Restart

Stop services while keeping volumes:

```powershell
docker compose --env-file .env -f infrastructure\docker\docker-compose.yaml down
```

Start again:

```powershell
docker compose --env-file .env -f infrastructure\docker\docker-compose.yaml up -d postgres redis minio
```

Remove containers and volumes:

```powershell
docker compose --env-file .env -f infrastructure\docker\docker-compose.yaml down -v
```

Only remove volumes when local data can be destroyed.

## Troubleshooting

### Compose Cannot Read Environment Values

Make sure `.env` exists in the repository root and service-level `.env` files exist under `services/<service>/.env`.

### PostgreSQL Login Fails

Run:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\setup_infrastructure.ps1
```

The script updates the local `agri_user` password to match `.env`.

### Ports Are Already In Use

The backend expects host ports `8000-8006`, PostgreSQL on `15432`, Redis on `6380`, and MinIO on `9000/9001`. Stop the conflicting service or update the Compose ports and service `.env` files together.

### AI Service Starts Without Real Model Artifacts

The AI service can pass health with its development default model behavior. Real staging or production inference requires valid model artifacts and active model registry metadata.

### Alembic Autogenerate Includes Other Services

Do not apply a migration that unexpectedly drops unrelated tables. Regenerate with:

```powershell
uv run python scripts\migration.py create --service model-registry -m "message" --autogenerate
```

Then review the generated revision before upgrading.

## Staging And Production Checklist

Before deploying outside local development:

- Replace all default secrets and passwords.
- Use managed PostgreSQL, Redis, and object storage or production-grade self-hosted equivalents.
- Configure TLS certificates for Nginx or the chosen ingress.
- Decide whether each service keeps a shared database or moves to service-specific databases.
- Initialize Alembic for every service that owns database tables.
- Add automated backup and restore testing for PostgreSQL and object storage.
- Configure structured log aggregation.
- Configure Prometheus scrape targets and Grafana dashboards.
- Set resource limits and health probes for the orchestrator.
- Decide GPU scheduling for AI service if production inference needs GPU.
- Store secrets in a secret manager instead of `.env` files.
- Run smoke tests and API checks in CI/CD before promotion.

## Recommended Promotion Flow

1. Build service images from a clean commit.
2. Run `docker compose config --quiet` or equivalent orchestrator validation.
3. Start infrastructure dependencies.
4. Apply migrations.
5. Start backend services.
6. Verify `/health` and `/ready` for every service.
7. Run a small API smoke set through the API Gateway.
8. Enable external traffic only after health, logs, and metrics are confirmed.
