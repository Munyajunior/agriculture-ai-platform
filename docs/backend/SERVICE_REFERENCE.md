# Backend Service Reference

This file is a deeper map of backend files, APIs, models, and scripts. Use it when you need to understand where a behavior lives or what to edit.

## Repository Backend Map

```text
services/
  api-gateway/
  auth-service/
  ai-service/
  analytics-service/
  media-service/
  model-registry/
  sync-service/
shared/
  types/
  inference-sdk/
  utilities/
scripts/
  smoke_backend.py
  migration.py
  setup_infrastructure.ps1
  run_backend_local.ps1
infrastructure/
  docker/
  nginx/
```

## API Gateway

Path:

```text
services/api-gateway
```

Important files:

| File | Purpose |
| --- | --- |
| `main.py` | Creates FastAPI app, lifespan, middleware, `/health`, `/ready`, router mount. |
| `app/config.py` | Gateway settings, service URLs, CORS, Redis URL, rate limit settings. |
| `app/api/v1/__init__.py` | Combines gateway routers under `/api/v1`. |
| `app/api/v1/auth.py` | Public auth proxy endpoints. |
| `app/api/v1/predictions.py` | Public prediction proxy endpoints. |
| `app/api/v1/analytics.py` | Public analytics proxy endpoints. |
| `app/api/v1/sync.py` | Public sync proxy endpoints. |
| `app/api/v1/devices.py` | Public device proxy endpoints. |
| `app/api/v1/models.py` | Public model registry proxy endpoints. |
| `app/clients/base.py` | Shared async HTTP client behavior for service clients. |
| `app/clients/auth_service.py` | Auth service HTTP client. |
| `app/clients/ai_service.py` | AI service HTTP client. |
| `app/clients/analytics_service.py` | Analytics service HTTP client. |
| `app/clients/media_service.py` | Media service HTTP client. |
| `app/clients/model_registry.py` | Model registry HTTP client. |
| `app/clients/sync_service.py` | Sync service HTTP client. |
| `app/middleware/auth.py` | JWT/auth middleware behavior. |
| `app/middleware/logging.py` | Request/response logging. |
| `app/core/rate_limiter.py` | Redis-backed rate limiting. |
| `app/core/redis_client.py` | Redis connection wrapper. |
| `app/schemas/*.py` | Gateway-facing request/response schemas. |

Mounted gateway endpoints:

| Prefix | File | Description |
| --- | --- | --- |
| `/api/v1/auth` | `app/api/v1/auth.py` | Register, login, refresh, logout, password workflows, profile. |
| `/api/v1/predict` | `app/api/v1/predictions.py` | Single prediction, batch prediction, image upload, history. |
| `/api/v1/analytics` | `app/api/v1/analytics.py` | Dashboard, diseases, engagement, performance, export. |
| `/api/v1/sync` | `app/api/v1/sync.py` | Upload offline data, pending sync, status, queue stats. |
| `/api/v1/devices` | `app/api/v1/devices.py` | Register/list/update/delete devices, telemetry, heartbeat. |
| `/api/v1/models` | `app/api/v1/models.py` | Active model, list models, register, activate, download, metrics. |

## Auth Service

Path:

```text
services/auth-service
```

Important files:

| File | Purpose |
| --- | --- |
| `main.py` | FastAPI app, DB/Redis/security startup, `/health`, `/ready`. |
| `app/config.py` | Auth settings: JWT, DB, Redis, CORS, email, OAuth, 2FA. |
| `app/core/database.py` | Async SQLAlchemy engine/session setup. |
| `app/core/security.py` | Password hashing, JWT, token helpers, role/permission logic. |
| `app/core/redis_client.py` | Redis token/session/cache helper. |
| `app/models/user.py` | Auth-local tables: API keys, OAuth accounts, password resets, sessions. |
| `app/models/__init__.py` | Package marker for auth model imports. |
| `app/schemas/auth.py` | Auth-specific request/response schemas and aliases. |
| `app/services/email_service.py` | Email sending for reset/verification workflows. |
| `app/api/dependencies.py` | Current-user and auth dependencies. |
| `app/api/v1/auth.py` | Register/login/token/logout/password/email endpoints. |
| `app/api/v1/users.py` | Current user profile and admin user operations. |
| `app/api/v1/oauth.py` | OAuth authorization/callback/account endpoints. |
| `app/api/v1/api_keys.py` | API key CRUD, rotation, admin listing. |
| `app/api/v1/sessions.py` | Session listing/revocation/admin cleanup. |

Mounted endpoints:

| Prefix | Key routes |
| --- | --- |
| `/api/v1/auth` | `POST /register`, `POST /login`, `POST /refresh`, `POST /logout`, `POST /forgot-password`, `POST /reset-password`, `POST /verify-email`, `POST /resend-verification` |
| `/api/v1/users` | `GET /me`, `PUT /me`, `GET /{user_id}`, `PUT /{user_id}/role`, `DELETE /{user_id}` |
| `/api/v1/oauth` | `GET /{provider}/authorize`, `POST /{provider}/callback`, `GET /accounts`, `DELETE /{provider}` |
| `/api/v1/api-keys` | `GET /`, `POST /`, `PUT /{key_id}/rotate`, `PATCH /{key_id}/toggle`, `DELETE /{key_id}`, `GET /admin/keys` |
| `/api/v1/sessions` | `GET /`, `GET /current`, `POST /{session_id}/revoke`, `POST /revoke-all`, `POST /refresh-activity`, admin session endpoints |

Tables:

| Table | Owner | Description |
| --- | --- | --- |
| `users` | shared types | Core user account data. |
| `api_keys` | auth | Programmatic access keys. |
| `oauth_accounts` | auth | Linked OAuth accounts. |
| `password_resets` | auth | Password reset tokens. |
| `sessions` | auth | User session records. |

## AI Service

Path:

```text
services/ai-service
```

Important files:

| File | Purpose |
| --- | --- |
| `main.py` | FastAPI app, DB startup, model registry startup, inference engine startup. |
| `app/config.py` | AI settings: DB, Redis, model paths, model type, ONNX/GPU flags, MinIO. |
| `app/core/database.py` | Async DB engine using shared platform models. |
| `app/core/inference_engine.py` | PyTorch/ONNX model loading and prediction flow. |
| `app/core/model_registry.py` | Client/cache for model registry metadata. |
| `app/models/mobilenetv3.py` | Model factory and MobileNetV3 architecture helpers. |
| `app/preprocessing/image_processor.py` | Image preprocessing for inference. |
| `app/services/prediction_service.py` | Higher-level prediction service logic. |
| `app/schemas/model.py` | Model metadata request/response schemas. |
| `app/worker.py` | Celery app placeholder/background worker integration. |
| `app/api/v1/predictions.py` | Prediction endpoints. |
| `app/api/v1/models.py` | Model metadata/cache endpoints. |
| `app/api/v1/health.py` | Detailed health/readiness/liveness/metrics endpoints. |

Mounted endpoints:

| Prefix | Key routes |
| --- | --- |
| `/api/v1/predict` | `POST /single`, `POST /batch`, `POST /upload`, `GET /history/{user_id}` |
| `/api/v1/models` | `GET /`, `GET /latest`, `GET /active`, `GET /{model_id}`, `POST /activate`, `POST /download`, `POST /validate`, `GET /metrics/{model_id}`, `DELETE /cache` |
| `/api/v1/health` | `GET /`, `GET /detailed`, `GET /readiness`, `GET /liveness`, `GET /metrics` |

Tables:

AI uses shared SQLAlchemy models from `shared/types/agriculture_ai/types/models.py`.

## Analytics Service

Path:

```text
services/analytics-service
```

Important files:

| File | Purpose |
| --- | --- |
| `main.py` | FastAPI app, DB/Redis/analytics engine/scheduler startup. |
| `app/config.py` | Compatibility import for core config. |
| `app/core/config.py` | Analytics settings: DB, Redis, security, CORS, reports, forecasts. |
| `app/core/database.py` | Async DB engine/session helper and DB health check. |
| `app/core/cache.py` | Redis cache wrapper. |
| `app/core/auth.py` | Auth compatibility helpers. |
| `app/scheduler.py` | APScheduler background jobs. |
| `app/services/analytics_engine.py` | Main analytics engine coordinator. |
| `app/services/predictive_analytics.py` | Predictive analytics model/service logic. |
| `app/services/metrics_service.py` | Service/platform metrics aggregation. |
| `app/services/report_generator.py` | Report generation logic. |
| `app/services/alert_service.py` | Alert rule/notification logic. |
| `app/schemas/analytics.py` | Dashboard/metrics/trend schemas. |
| `app/schemas/reports.py` | Report request/response schemas. |
| `app/schemas/alerts.py` | Alert schemas. |
| `app/api/v1/dashboard.py` | Dashboard endpoints. |
| `app/api/v1/diseases.py` | Disease statistics/trends endpoints. |
| `app/api/v1/analytics.py` | Analytics query endpoints. |
| `app/api/v1/reports.py` | Report generation/download/list endpoints. |
| `app/api/v1/alerts.py` | Alert rule/notification endpoints. |

Mounted endpoints:

| Prefix | Key routes |
| --- | --- |
| `/api/v1/dashboard` | `GET /summary`, `GET /timeseries`, `GET /disease-distribution`, `GET /performance-metrics`, `GET /user-activity`, `GET /realtime`, `GET /geospatial` |
| `/api/v1/diseases` | `GET /statistics`, `GET /trends/{disease_type}`, `GET /comparison`, `GET /hotspots` |
| `/api/v1/analytics` | `GET /dashboard`, `GET /diseases/trends`, `GET /geo/distribution`, `GET /performance/model` |
| `/api/v1/reports` | `POST /generate`, `GET /status/{task_id}`, `GET /download/{task_id}`, `GET /list`, `DELETE /{report_id}`, `POST /schedule`, `GET /export/dashboard` |
| `/api/v1/alerts` | `GET /rules`, `POST /rules`, `PUT /rules/{rule_id}`, `DELETE /rules/{rule_id}`, notification endpoints |

Tables:

No service-local SQLAlchemy metadata is currently exposed. It uses DB connectivity for analytics queries and future persisted analytics tables.

## Media Service

Path:

```text
services/media-service
```

Important files:

| File | Purpose |
| --- | --- |
| `main.py` | FastAPI app, DB/storage/cache/thumbnail-worker startup. |
| `app/config.py` | Media settings: DB, Redis, MinIO/S3/local storage, CORS, rate limits. |
| `app/database.py` | SQLAlchemy media tables and DB session/helper. |
| `app/storage.py` | Unified storage implementation using boto3 for MinIO/S3/R2/local. |
| `app/core/storage.py` | Compatibility wrapper exposing `StorageManager`. |
| `app/core/cache.py` | Redis-backed media cache. |
| `app/core/image_processor.py` | Image validation, thumbnails, processing helpers. |
| `app/dependencies.py` | Upload/download dependencies. |
| `app/middleware.py` | Request logging middleware. |
| `app/workers/thumbnail_worker.py` | Background thumbnail worker. |
| `app/api/v1/upload.py` | Image upload and chunked upload endpoints. |
| `app/api/v1/download.py` | Image, thumbnail, and batch download endpoints. |

Mounted endpoints:

| Prefix | Key routes |
| --- | --- |
| `/api/v1/upload` | `POST /image`, `POST /chunked/initiate`, `POST /chunked/upload`, `POST /chunked/complete` |
| `/api/v1/download` | `GET /image/{media_id}`, `GET /thumbnail/{user_id}/{size}/{filename}`, `GET /batch` |

Tables:

| Table | Description |
| --- | --- |
| `media_files` | Image/object metadata, thumbnail paths, tags, processing status. |
| `upload_sessions` | Chunked upload sessions and completed chunk tracking. |
| `image_analysis` | Image quality/plant/disease/color analysis metadata. |

## Model Registry

Path:

```text
services/model-registry
```

Important files:

| File | Purpose |
| --- | --- |
| `main.py` | FastAPI app, DB/storage/registry/model-manager startup. |
| `app/config.py` | Registry settings: DB, Redis, model storage, MLflow, CORS, API key. |
| `app/database.py` | SQLAlchemy model registry tables and dev-safe schema repair. |
| `app/core/storage.py` | Local model artifact storage helper. |
| `app/core/registry.py` | Model version registry business logic. |
| `app/core/model_manager.py` | Runtime model loading/unloading and inference wrapper. |
| `app/models/architectures.py` | Model architecture registry/placeholders. |
| `app/monitoring.py` | Model monitoring placeholder/service. |
| `app/schemas.py` | Registry Pydantic request/response schemas. |
| `app/api/v1/models.py` | Model registration/list/status/promote/download endpoints. |
| `app/api/v1/deployment.py` | Deployment and rollback endpoints. |
| `app/api/v1/metrics.py` | Model metric recording/query endpoints. |
| `alembic.ini` | Service Alembic config. |
| `migrations/env.py` | Alembic env with service-table filtering. |
| `migrations/versions/*.py` | Alembic migration revisions. |

Mounted endpoints:

| Prefix | Key routes |
| --- | --- |
| `/api/v1/models` | `POST /register`, `GET /`, `GET /active`, `GET /{model_id}`, `PUT /{model_id}/status`, `POST /{model_id}/promote`, `POST /compare`, `GET /{model_id}/download` |
| `/api/v1/deployments` | `POST /{model_id}/deploy`, `GET /{model_id}/deployments`, `GET /deployments/active`, `POST /deployments/{deployment_id}/rollback` |
| `/api/v1/metrics` | `POST /{model_id}/metrics`, `GET /{model_id}/metrics`, `GET /{model_id}/metrics/summary`, `GET /models/compare` |

Tables:

| Table | Description |
| --- | --- |
| `model_versions` | Model metadata, paths, framework, shape, metrics, status, active flags. |
| `model_deployments` | Deployment history and rollback metadata. |
| `model_metrics` | Runtime/model performance metrics over time. |
| `model_experiments` | Experiment/run metadata and artifacts. |

Alembic:

| File | Purpose |
| --- | --- |
| `services/model-registry/alembic.ini` | Alembic configuration for this service. |
| `services/model-registry/migrations/env.py` | Loads service env and metadata; filters autogenerate to registry-owned tables. |
| `services/model-registry/migrations/script.py.mako` | Template for generated revision files. |
| `services/model-registry/migrations/versions/10d82dd979df_baseline_model_registry.py` | Current baseline revision. |

## Sync Service

Path:

```text
services/sync-service
```

Important files:

| File | Purpose |
| --- | --- |
| `main.py` | FastAPI app, DB/queue/sync-engine/worker startup. |
| `app/config.py` | Sync settings: DB, Redis, worker counts, retry, conflict strategy, rate limits. |
| `app/database.py` | SQLAlchemy sync tables and enums. |
| `app/schemas.py` | Sync/device/conflict request/response schemas. |
| `app/core/queue_manager.py` | Redis-backed sync queue manager. |
| `app/core/sync_engine.py` | Sync processing and status logic. |
| `app/core/conflict_resolver.py` | Conflict resolution logic. |
| `app/workers/sync_worker.py` | Background sync workers. |
| `app/api/v1/sync.py` | Sync and queue endpoints. |
| `app/api/v1/devices.py` | Device registration/heartbeat/listing endpoints. |
| `app/api/v1/conflicts.py` | Conflict listing/resolution endpoints. |

Mounted endpoints:

| Prefix | Key routes |
| --- | --- |
| `/api/v1/sync` | `POST /`, `POST /batch`, `GET /status/{device_id}`, `POST /queue/add`, `POST /queue/process`, `DELETE /queue/{item_id}` |
| `/api/v1/devices` | `POST /register`, `POST /heartbeat`, `GET /`, `GET /{device_id}`, `DELETE /{device_id}` |
| `/api/v1/conflicts` | `GET /`, `GET /{conflict_id}`, `POST /{conflict_id}/resolve`, `POST /{conflict_id}/resolve/auto`, `DELETE /{conflict_id}`, `GET /stats` |

Tables:

| Table | Description |
| --- | --- |
| `sync_queue` | Pending sync operations. |
| `sync_logs` | Sync attempt/result logs. |
| `sync_conflicts` | Conflict records requiring resolution. |
| `device_sync_state` | Last known device sync state and heartbeat info. |

Enums:

| Enum | Purpose |
| --- | --- |
| `SyncStatus` | Pending, processing, completed, failed, conflict, cancelled. |
| `EntityType` | Entity categories being synchronized. |
| `ConflictStrategy` | Resolution behavior such as server/client/last-write/merge. |

## Shared Types

Path:

```text
shared/types
```

Important files:

| File | Purpose |
| --- | --- |
| `agriculture_ai/types/models.py` | Shared SQLAlchemy Base and platform tables. |
| `agriculture_ai/types/schemas.py` | Shared Pydantic schemas. |
| `agriculture_ai/types/enums.py` | Shared enum definitions. |
| `pyproject.toml` | Package definition for `agriculture-shared-types`. |

Shared tables:

| Table | Purpose |
| --- | --- |
| `users` | Platform users. |
| `farms` | Farm/crop/location data. |
| `scans` | Captured image scan metadata. |
| `predictions` | Disease prediction outputs. |
| `diseases` | Disease catalog. |
| `treatments` | Treatment recommendations. |
| `devices` | Device registry. |
| `telemetry` | Device telemetry. |
| `model_versions` | Shared model metadata table. |
| `sync_logs` | Shared sync log table. |

## Shared Inference SDK

Path:

```text
shared/inference-sdk
```

Important files:

| File | Purpose |
| --- | --- |
| `agriculture_inference/preprocessing.py` | Shared preprocessing helpers. |
| `agriculture_inference/model_manager.py` | Shared model manager helpers. |
| `agriculture_inference/inference_engine.py` | Shared inference execution helpers. |
| `agriculture_inference/hybrid_inference.py` | Hybrid/local-cloud inference helpers. |

## Shared Utilities

Path:

```text
shared/utilities
```

Important files:

| File | Purpose |
| --- | --- |
| `agriculture_utils/async_utils.py` | Async helper functions. |
| `agriculture_utils/datetime_utils.py` | Datetime helper functions. |
| `agriculture_utils/geometry_utils.py` | Geometry/location helpers. |
| `agriculture_utils/http_utils.py` | HTTP helper functions. |
| `agriculture_utils/image_utils.py` | Image helper functions. |
| `agriculture_utils/logging_utils.py` | Logging helper functions. |
| `agriculture_utils/postprocessing.py` | Prediction postprocessing helpers. |
| `agriculture_utils/validators.py` | Validation helpers. |

## Backend Scripts

| Script | Purpose |
| --- | --- |
| `scripts/setup_infrastructure.ps1` | Start/create PostgreSQL, Redis, MinIO; repair DB password; create MinIO buckets; optionally start backend containers. |
| `scripts/run_backend_local.ps1` | Run infrastructure setup, then keep local backend services running for browser/API use. |
| `scripts/smoke_backend.py` | Start each service locally, call `/health`, terminate service, and report output. Use `--keep-alive` to keep all services running until `Ctrl+C`. |
| `scripts/migration.py` | Manage SQLAlchemy metadata operations and Alembic workflows. |

## Infrastructure Files

| File | Purpose |
| --- | --- |
| `infrastructure/docker/docker-compose.yaml` | Local compose stack for infra and backend services. |
| `infrastructure/docker/Dockerfile.api-gateway` | API gateway image. |
| `infrastructure/docker/Dockerfile.auth-service` | Auth service image. |
| `infrastructure/docker/Dockerfile.ai-service` | AI service image. |
| `infrastructure/docker/Dockerfile.analytics-service` | Analytics service image. |
| `infrastructure/docker/Dockerfile.media-service` | Media service image. |
| `infrastructure/docker/Dockerfile.model-registry` | Model registry image. |
| `infrastructure/docker/Dockerfile.sync-service` | Sync service image. |
| `infrastructure/docker/init-db.sql` | PostgreSQL initialization SQL. |
| `infrastructure/docker/prometheus.yml` | Prometheus config. |
| `infrastructure/nginx/nginx.conf` | Nginx reverse proxy config. |

## How To Read The Codebase

For a non-engineer:

1. Start with `docs/backend/README.md`.
2. Read the service summary table.
3. Use this reference to find the service that owns the feature.
4. Open that service's `main.py` to see startup behavior.
5. Open `app/api/v1/*.py` to see what external calls exist.
6. Open `app/database.py` or `app/core/database.py` to see what data is stored.

For a developer:

1. Start infrastructure with `scripts/setup_infrastructure.ps1`.
2. Run `scripts/smoke_backend.py`, or run `scripts/run_backend_local.ps1` when you need the services to stay available.
3. Use API docs at `http://127.0.0.1:<port>/docs` or `/api/docs`.
4. Use `scripts/migration.py` before and after model/table changes.
5. Run `git diff --check` and smoke test before committing backend changes.
