# Backend API Reference

This document explains how to call the completed backend APIs. It is written around the local development setup that has been verified with `scripts/smoke_backend.py`.

## API Strategy

Clients should normally call the API Gateway on port `8000`. The gateway exposes the public backend surface and forwards requests to the internal services.

Direct service calls are still useful for development, debugging, and service-specific testing. Each FastAPI service also exposes its own interactive OpenAPI page.

| Entry Point | Local URL | Use |
| --- | --- | --- |
| API Gateway | `http://127.0.0.1:8000` | Main client-facing backend API. |
| Auth Service | `http://127.0.0.1:8001` | Direct auth debugging. |
| AI Service | `http://127.0.0.1:8002` | Direct prediction/model debugging. |
| Analytics Service | `http://127.0.0.1:8003` | Direct dashboard/report debugging. |
| Media Service | `http://127.0.0.1:8004` | Direct upload/download debugging. |
| Model Registry | `http://127.0.0.1:8005` | Direct model lifecycle debugging. |
| Sync Service | `http://127.0.0.1:8006` | Direct offline sync/device debugging. |

## Interactive API Docs

| Service | Docs URL |
| --- | --- |
| API Gateway | `http://127.0.0.1:8000/api/docs` |
| Auth Service | `http://127.0.0.1:8001/api/docs` |
| AI Service | `http://127.0.0.1:8002/docs` |
| Analytics Service | `http://127.0.0.1:8003/docs` |
| Media Service | `http://127.0.0.1:8004/api/docs` |
| Model Registry | `http://127.0.0.1:8005/api/docs` |
| Sync Service | `http://127.0.0.1:8006/api/docs` |

Use these pages when you need exact request and response schemas. This file gives the human map: what each API group is for, which service owns it, and which routes exist.

## Health APIs

Every backend service exposes:

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/health` | Basic process health check. |
| `GET` | `/ready` | Readiness check for dependencies and startup state. |

The AI service also exposes detailed health routes under `/api/v1/health`.

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/api/v1/health/` | AI service health. |
| `GET` | `/api/v1/health/detailed` | Detailed dependency/model health. |
| `GET` | `/api/v1/health/readiness` | AI readiness probe. |
| `GET` | `/api/v1/health/liveness` | AI liveness probe. |
| `GET` | `/api/v1/health/metrics` | AI health metrics. |

## Authentication

Authenticated requests use a bearer token:

```http
Authorization: Bearer <access_token>
```

The token is returned by login and refresh calls. Admin-only routes additionally require a user role with permission for that operation.

Common status codes:

| Code | Meaning |
| ---: | --- |
| `200` | Request succeeded. |
| `201` | Resource created. |
| `400` | Invalid business request. |
| `401` | Missing, invalid, or expired credentials. |
| `403` | Authenticated but not allowed. |
| `404` | Resource not found. |
| `422` | FastAPI validation failed. |
| `429` | Rate limit exceeded. |
| `500` | Service error. |
| `502` | Gateway could not get a valid upstream response. |
| `503` | Service or dependency unavailable. |

## Gateway APIs

Base URL:

```text
http://127.0.0.1:8000/api/v1
```

### Gateway Auth

| Method | Path | Purpose |
| --- | --- | --- |
| `POST` | `/auth/register` | Create a user account. |
| `POST` | `/auth/login` | Login and receive access/refresh tokens. |
| `POST` | `/auth/refresh` | Refresh tokens. |
| `POST` | `/auth/logout` | Revoke/logout current session. |
| `POST` | `/auth/change-password` | Change password for an authenticated user. |
| `POST` | `/auth/forgot-password` | Start password reset. |
| `POST` | `/auth/reset-password` | Complete password reset. |
| `GET` | `/auth/me` | Return current user profile. |
| `PUT` | `/auth/me` | Update current user profile. |

Example login:

```powershell
curl.exe -X POST http://127.0.0.1:8000/api/v1/auth/login `
  -H "Content-Type: application/json" `
  -d "{\"email\":\"user@example.com\",\"password\":\"password\"}"
```

### Gateway Predictions

| Method | Path | Purpose |
| --- | --- | --- |
| `POST` | `/predict/single` | Run one prediction from structured input. |
| `POST` | `/predict/batch` | Run multiple predictions. |
| `POST` | `/predict/upload-image` | Upload an image and request prediction. |
| `GET` | `/predict/history/{user_id}` | Get prediction history for a user. |
| `GET` | `/predict/{prediction_id}` | Get a specific prediction. |

### Gateway Analytics

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/analytics/dashboard` | Dashboard summary. |
| `GET` | `/analytics/diseases` | Disease analytics. |
| `GET` | `/analytics/engagement` | User/device engagement analytics. |
| `GET` | `/analytics/performance` | Platform/model performance analytics. |
| `GET` | `/analytics/export` | Export analytics data. |

### Gateway Sync

| Method | Path | Purpose |
| --- | --- | --- |
| `POST` | `/sync/upload` | Upload sync payload. |
| `GET` | `/sync/pending` | List pending sync work. |
| `GET` | `/sync/status/{sync_id}` | Get sync item status. |
| `GET` | `/sync/queue/stats` | Get queue statistics. |

### Gateway Devices

| Method | Path | Purpose |
| --- | --- | --- |
| `POST` | `/devices/register` | Register a device. |
| `GET` | `/devices/` | List devices. |
| `GET` | `/devices/{device_id}` | Get one device. |
| `PUT` | `/devices/{device_id}` | Update device metadata. |
| `DELETE` | `/devices/{device_id}` | Delete/deactivate a device. |
| `POST` | `/devices/{device_id}/telemetry` | Submit telemetry. |
| `POST` | `/devices/{device_id}/heartbeat` | Submit heartbeat. |

### Gateway Models

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/models/active` | Get active model. |
| `GET` | `/models/` | List models. |
| `GET` | `/models/{model_id}` | Get model metadata. |
| `POST` | `/models/register` | Register model metadata. |
| `PUT` | `/models/{model_id}/activate` | Activate a model. |
| `GET` | `/models/{model_id}/download` | Get model download details. |
| `GET` | `/models/{model_id}/metrics` | Get model metrics. |

## Direct Service APIs

### Auth Service

Base URL:

```text
http://127.0.0.1:8001/api/v1
```

| Group | Routes |
| --- | --- |
| Auth | `POST /auth/register`, `POST /auth/login`, `POST /auth/refresh`, `POST /auth/logout`, `POST /auth/forgot-password`, `POST /auth/reset-password`, `POST /auth/verify-email`, `POST /auth/resend-verification` |
| Users | `GET /users/me`, `PUT /users/me`, `POST /users/me/change-password`, `GET /users/{user_id}`, `PUT /users/{user_id}/role`, `DELETE /users/{user_id}` |
| Sessions | `GET /sessions/`, `GET /sessions/current`, `POST /sessions/{session_id}/revoke`, `POST /sessions/revoke-all`, `POST /sessions/refresh-activity`, `GET /sessions/admin/sessions`, `DELETE /sessions/admin/sessions/{session_id}`, `DELETE /sessions/admin/expired` |
| API Keys | `GET /api-keys/`, `POST /api-keys/`, `PUT /api-keys/{key_id}/rotate`, `PATCH /api-keys/{key_id}/toggle`, `DELETE /api-keys/{key_id}`, `GET /api-keys/admin/keys` |
| OAuth | `GET /oauth/{provider}/authorize`, `POST /oauth/{provider}/callback`, `GET /oauth/accounts`, `DELETE /oauth/{provider}` |

### AI Service

Base URL:

```text
http://127.0.0.1:8002/api/v1
```

| Group | Routes |
| --- | --- |
| Predictions | `POST /predict/single`, `POST /predict/batch`, `POST /predict/upload`, `GET /predict/history/{user_id}` |
| Models | `GET /models/`, `GET /models/latest`, `GET /models/active`, `GET /models/{model_id}`, `POST /models/activate`, `POST /models/download`, `POST /models/validate`, `GET /models/metrics/{model_id}`, `DELETE /models/cache` |
| Health | `GET /health/`, `GET /health/detailed`, `GET /health/readiness`, `GET /health/liveness`, `GET /health/metrics` |

### Analytics Service

Base URL:

```text
http://127.0.0.1:8003/api/v1
```

| Group | Routes |
| --- | --- |
| Dashboard | `GET /dashboard/summary`, `GET /dashboard/timeseries`, `GET /dashboard/disease-distribution`, `GET /dashboard/performance-metrics`, `GET /dashboard/user-activity`, `GET /dashboard/realtime`, `GET /dashboard/geospatial` |
| Analytics | `GET /analytics/dashboard`, `GET /analytics/diseases/trends`, `GET /analytics/geo/distribution`, `GET /analytics/performance/model` |
| Diseases | `GET /diseases/statistics`, `GET /diseases/trends/{disease_type}`, `GET /diseases/comparison`, `GET /diseases/hotspots` |
| Reports | `POST /reports/generate`, `GET /reports/status/{task_id}`, `GET /reports/download/{task_id}`, `GET /reports/list`, `DELETE /reports/{report_id}`, `POST /reports/schedule`, `GET /reports/export/dashboard` |
| Alerts | `GET /alerts/rules`, `POST /alerts/rules`, `PUT /alerts/rules/{rule_id}`, `DELETE /alerts/rules/{rule_id}`, `GET /alerts/notifications`, `POST /alerts/notifications/{notification_id}/acknowledge`, `POST /alerts/notifications/mark-read`, `GET /alerts/check` |

### Media Service

Base URL:

```text
http://127.0.0.1:8004/api/v1
```

| Group | Routes |
| --- | --- |
| Upload | `POST /upload/image`, `POST /upload/chunked/initiate`, `POST /upload/chunked/upload`, `POST /upload/chunked/complete` |
| Download | `GET /download/image/{media_id}`, `GET /download/thumbnail/{user_id}/{size}/{filename}`, `GET /download/batch` |

### Model Registry

Base URL:

```text
http://127.0.0.1:8005/api/v1
```

| Group | Routes |
| --- | --- |
| Models | `POST /models/register`, `GET /models/`, `GET /models/active`, `GET /models/{model_id}`, `PUT /models/{model_id}/status`, `POST /models/{model_id}/promote`, `POST /models/compare`, `GET /models/{model_id}/download` |
| Deployments | `POST /deployments/{model_id}/deploy`, `GET /deployments/{model_id}/deployments`, `GET /deployments/deployments/active`, `POST /deployments/deployments/{deployment_id}/rollback` |
| Metrics | `POST /metrics/{model_id}/metrics`, `GET /metrics/{model_id}/metrics`, `GET /metrics/{model_id}/metrics/summary`, `GET /metrics/models/compare` |

The repeated `deployments` segment in some deployment paths comes from the current router prefix plus route path. Use the interactive docs as the source of truth if this API changes.

### Sync Service

Base URL:

```text
http://127.0.0.1:8006/api/v1
```

| Group | Routes |
| --- | --- |
| Sync | `POST /sync/`, `POST /sync/batch`, `GET /sync/status/{device_id}`, `POST /sync/queue/add`, `POST /sync/queue/process`, `DELETE /sync/queue/{item_id}` |
| Devices | `POST /devices/register`, `POST /devices/heartbeat`, `GET /devices/`, `GET /devices/{device_id}`, `DELETE /devices/{device_id}` |
| Conflicts | `GET /conflicts/`, `GET /conflicts/{conflict_id}`, `POST /conflicts/{conflict_id}/resolve`, `POST /conflicts/{conflict_id}/resolve/auto`, `DELETE /conflicts/{conflict_id}`, `GET /conflicts/stats` |

## Practical API Workflow

A typical client flow is:

1. Register or login through `POST /api/v1/auth/login`.
2. Store the returned access token in the client.
3. Send `Authorization: Bearer <token>` on authenticated API calls.
4. Upload media through the gateway or media service.
5. Request prediction through `/api/v1/predict/*`.
6. Read analytics and history through gateway analytics/prediction routes.
7. For offline clients, register the device and submit sync batches.

For exact request body fields, use the interactive OpenAPI docs for the service you are calling.
