# Agriculture AI Platform

Agriculture AI Platform is a backend-first, microservice-based system for plant disease detection, model serving, media handling, analytics, offline synchronization, and device workflows.

This repository is still being completed in stages. The backend services, local infrastructure setup, health smoke test, and migration tooling are the currently documented and verified parts.

## Current Backend Status

The local backend has been verified with:

```powershell
uv run python scripts\smoke_backend.py
```

All seven backend services pass `/health` when local infrastructure is running:

- API Gateway
- Auth Service
- AI Service
- Analytics Service
- Media Service
- Model Registry
- Sync Service

## Start Here

Read the backend guide:

[Backend Documentation](docs/backend/README.md)

For detailed file-by-file service reference:

[Backend Service Reference](docs/backend/SERVICE_REFERENCE.md)

Focused backend references:

- [Backend API Reference](docs/backend/API.md)
- [Backend Architecture](docs/backend/ARCHITECTURE.md)
- [Backend Deployment Guide](docs/backend/DEPLOYMENT.md)

Training reference:

- [Model Training](docs/training/MODEL_TRAINING.md)

## Common Commands

Start local infrastructure and run the backend smoke test:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\run_backend_local.ps1
```

Start only infrastructure:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\setup_infrastructure.ps1
```

Run backend smoke test:

```powershell
uv run python scripts\smoke_backend.py
```

Run migration helper:

```powershell
uv run python scripts\migration.py list
```

## Documentation Scope

The current docs focus on backend services, completed local infrastructure, and the first model-training workflow. Frontend, mobile, hardened production operations, and edge-device workflows will be expanded as those parts are completed.
