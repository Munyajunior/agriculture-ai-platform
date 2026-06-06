# Backend Architecture

This document explains how the completed backend is organized, how services communicate, and where data lives.

## System Shape

The backend is a FastAPI microservice system. Each service owns one domain, while shared packages provide common models, schemas, enums, and utility code.

```text
Clients
  |
  v
API Gateway :8000
  |
  +--> Auth Service :8001 -------- PostgreSQL
  +--> AI Service :8002 ---------- PostgreSQL, Redis, MinIO, Model Registry
  +--> Analytics Service :8003 --- PostgreSQL, Redis
  +--> Media Service :8004 ------- PostgreSQL, Redis, MinIO
  +--> Model Registry :8005 ------ PostgreSQL, Redis, MinIO
  +--> Sync Service :8006 -------- PostgreSQL, Redis

Shared packages:
  shared/types
  shared/inference-sdk
  shared/utilities
```

Local infrastructure runs in Docker. Services can run directly with `uvicorn` during smoke testing, or they can run as Docker Compose services.

## Layers

| Layer | Contents | Responsibility |
| --- | --- | --- |
| Client edge | Frontend, mobile app, edge clients | Calls the API Gateway. |
| Gateway | `services/api-gateway` | Public API surface, request forwarding, auth middleware, rate limiting, CORS, logging. |
| Domain services | `services/*-service` | Own business behavior for auth, prediction, media, analytics, model lifecycle, and sync. |
| Shared packages | `shared/types`, `shared/inference-sdk`, `shared/utilities` | Reusable models, schemas, enums, inference helpers, image helpers, logging, validation, HTTP helpers. |
| Infrastructure | PostgreSQL, Redis, MinIO | Persistent relational data, cache/queues, object/model storage. |
| Operations scripts | `scripts/*.py`, `scripts/*.ps1` | Local setup, smoke checks, and migration management. |

## Service Responsibilities

| Service | Owns | Does Not Own |
| --- | --- | --- |
| API Gateway | Public route organization, forwarding, client-facing schemas | Long-running business logic or persistent domain data. |
| Auth Service | Users, passwords, tokens, sessions, OAuth, API keys | Prediction, media storage, analytics calculations. |
| AI Service | Inference requests, model loading, prediction response shape | Model registry metadata ownership or artifact lifecycle policy. |
| Analytics Service | Dashboard, trends, reports, alerts | Raw media storage or authentication. |
| Media Service | Images, chunks, thumbnails, MinIO object IO | Disease inference or model deployment decisions. |
| Model Registry | Model versions, metrics, deployments, artifact references | User sessions or image uploads. |
| Sync Service | Offline queues, device state, conflict resolution | Analytics calculations or prediction execution. |

## Data Ownership

The backend currently uses one PostgreSQL database for local development, with service-owned tables inside that database. The migration helper uses service metadata so tables can be created, dropped, or migrated per service.

| Data Group | Owner | Storage |
| --- | --- | --- |
| Users and shared platform entities | Shared types, used by Auth and other services | PostgreSQL |
| Auth sessions, API keys, OAuth accounts | Auth Service | PostgreSQL, Redis for fast token/session behavior |
| Predictions and scans | Shared types and AI-facing workflows | PostgreSQL |
| Uploaded images and thumbnails | Media Service | PostgreSQL metadata, MinIO objects, Redis cache |
| Model versions, deployments, metrics | Model Registry | PostgreSQL metadata, MinIO/model volume artifacts |
| Offline sync queue, logs, conflicts, devices | Sync Service | PostgreSQL, Redis queue/cache |
| Analytics reports and alerts | Analytics Service | PostgreSQL/Redis-backed runtime services |

## Request Flow: Login

```text
Client
  -> API Gateway /api/v1/auth/login
  -> Auth Service /api/v1/auth/login
  -> PostgreSQL user/session lookup
  <- access token and refresh token
```

Clients then send the access token as `Authorization: Bearer <token>`.

## Request Flow: Prediction

```text
Client
  -> API Gateway /api/v1/predict/single or /upload-image
  -> AI Service /api/v1/predict/*
  -> model loaded from local cache or registry configuration
  -> optional PostgreSQL prediction/history write
  <- disease prediction response
```

For image-based workflows, clients may upload media first, then reference the uploaded image in a prediction request.

## Request Flow: Media Upload

```text
Client
  -> API Gateway or Media Service
  -> Media Service /api/v1/upload/image
  -> validation and metadata write
  -> MinIO object write
  -> optional thumbnail/cache work
  <- media id and download information
```

Large uploads can use the chunked upload API:

```text
initiate -> upload chunk(s) -> complete
```

## Request Flow: Model Lifecycle

```text
Developer or admin
  -> Model Registry /api/v1/models/register
  -> model metadata stored in PostgreSQL
  -> artifact reference stored for MinIO/model storage
  -> metrics recorded through /api/v1/metrics/*
  -> deployment tracked through /api/v1/deployments/*
  -> AI Service reads active/default model configuration
```

Only model-registry currently has Alembic initialized. Other metadata-backed services can still use SQLAlchemy table create/drop/reset through `scripts/migration.py`.

## Request Flow: Offline Sync

```text
Device
  -> register or heartbeat
  -> upload sync batch
  -> Sync Service validates queue items
  -> conflicts are detected and stored
  -> user/admin or auto resolver resolves conflicts
```

This supports offline-first clients that collect data without a permanent network connection.

## Runtime Configuration

Configuration is environment-driven.

| Runtime | Database URL | Redis URL | Object Storage |
| --- | --- | --- | --- |
| Local direct services | `127.0.0.1:15432` | `127.0.0.1:6380` | `localhost:9000` |
| Docker Compose services | `postgres:5432` | `redis:6379` | `minio:9000` |

Root `.env` contains shared defaults. Each service has `services/<service>/.env` for service-specific settings.

## Cross-Cutting Concerns

| Concern | Current Implementation |
| --- | --- |
| API docs | FastAPI OpenAPI docs per service. |
| Health checks | `/health` and `/ready` per service. |
| Auth | JWT-based auth through auth service and gateway middleware. |
| Rate limiting | Gateway middleware. |
| CORS | Gateway and service configuration. |
| Logging | Service logging helpers and request middleware. |
| Database | SQLAlchemy async engines/sessions where services own metadata. |
| Migrations | `scripts/migration.py`; Alembic initialized for model-registry. |
| Cache/queue | Redis. |
| Object storage | MinIO locally, S3-compatible storage abstraction in media/model services. |
| Smoke verification | `scripts/smoke_backend.py` starts each service and checks `/health`. |

## Shared Code Policy

Use shared code when behavior crosses service boundaries:

| Shared Package | Use For |
| --- | --- |
| `shared/types` | Shared SQLAlchemy models, enums, and Pydantic schemas. |
| `shared/inference-sdk` | Model loading, inference helpers, preprocessing, postprocessing. |
| `shared/utilities` | Async helpers, datetime, geometry, image processing, HTTP helpers, logging, validation. |

Service-local code should remain service-local when it is only useful to one service. Shared abstractions should be added when they remove real duplication or define a platform contract.

## Current Architecture Limits

- Local development uses one shared PostgreSQL database. Production can still separate databases by service later if needed.
- Alembic is initialized only for model-registry right now.
- Analytics does not currently expose service-local SQLAlchemy metadata to the migration helper.
- AI health can pass with a development default model; production inference needs real model artifacts.
- Nginx, Prometheus, and Grafana are present in Compose, but production observability and TLS hardening are not completed in this documentation pass.
