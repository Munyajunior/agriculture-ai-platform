MASTER AI DEVELOPMENT PROMPT

Hybrid AI-Powered Plant Disease Detection Platform (Mobile + Web MVP, Edge-Ready Architecture)

You are a senior AI architect, full-stack engineer, DevOps engineer, MLOps engineer, cloud architect, mobile engineer, and systems designer responsible for building a complete production-ready software platform from start to finish.

Your task is to design and develop a fully functional, scalable, modular, enterprise-grade Hybrid AI Agriculture Intelligence Platform focused initially on automatic plant disease detection for mobile and web platforms while architecting the system from day one for future edge AI, drones, UAVs, IoT devices, and embedded systems without requiring rewrites.

The system must support BOTH:

1. Cloud inference
2. Edge/local inference

using a shared backend ecosystem and shared AI infrastructure.

The final result should be a cohesive, production-ready codebase with complete architecture, implementation, deployment, documentation, and operational guidance.

---

# PRODUCT OVERVIEW

Build a hybrid AI-powered plant disease detection platform that allows users to:

* Capture or upload plant images
* Detect plant diseases using AI
* Receive treatment recommendations
* Operate online and offline
* Sync offline results when internet becomes available
* Scale later to support drones, UAVs, IoT devices, and edge AI systems

The MVP should focus on:

* Mobile application
* Web dashboard
* Cloud AI inference
* Edge-ready ONNX inference support
* Modular backend architecture

The architecture MUST be designed from the beginning to support:

* Edge AI deployment
* Drone integrations
* UAV telemetry
* Jetson deployment
* Raspberry Pi deployment
* Real-time video inference
* Autonomous agriculture systems

without architectural rewrites.

---

# CORE PRODUCT FEATURES

## Farmer Mobile Features

* User registration/login
* Camera capture
* Gallery image upload
* Plant disease detection
* AI confidence scores
* Treatment recommendations
* Scan history
* Offline mode
* Local image queueing
* Automatic synchronization

---

## Admin Web Dashboard Features

* User management
* Disease analytics
* AI prediction monitoring
* Uploaded scan review
* Dataset management
* Manual prediction verification
* Model version management
* Platform statistics

---

## AI Features

* Plant disease classification
* Confidence scoring
* Lightweight edge inference
* Cloud verification inference
* Recommendation engine
* Model versioning
* ONNX export support

---

# HYBRID ARCHITECTURE REQUIREMENTS

The system MUST implement hybrid AI architecture:

## Cloud Inference

* Backend GPU/CPU inference
* Advanced AI verification
* Centralized analytics

## Edge Inference

* Local ONNX inference on mobile
* Offline prediction support
* Local preprocessing
* Sync engine

The mobile app must support:

* Online cloud inference
* Offline local inference
* Hybrid fallback logic

Example flow:

1. User captures image
2. Local ONNX model performs instant prediction
3. If the internet is available:

   * send image to cloud
   * run advanced verification
   * return enhanced result
4. If offline:

   * save locally
   * sync later automatically

---

# TARGET MVP CROPS

Start with:

* Tomato
* Cassava
* Maize

---

# TARGET MVP DISEASES

Include approximately 10–15 diseases total.

Examples:

* Tomato Early Blight
* Tomato Late Blight
* Cassava Mosaic Disease
* Maize Rust

---

# REQUIRED TECHNOLOGY STACK

You MUST use the following technologies unless a strong technical justification exists.

---

# FRONTEND

## Mobile App

Framework:

* Flutter

Architecture:

* Clean Architecture
* Riverpod state management

Requirements:

* Offline-first architecture
* Local storage
* Camera integration
* ONNX Runtime Mobile integration
* Background sync engine

---

## Web Dashboard

Framework:

* Next.js
* TypeScript
* TailwindCSS

Requirements:

* Admin dashboard
* Analytics
* User management
* Responsive UI

---

# BACKEND

Framework:

* FastAPI

Requirements:

* Async architecture
* REST APIs
* OpenAPI documentation
* JWT authentication
* Role-based access control
* Modular microservices architecture

---

# AI/ML STACK

Training:

* PyTorch

Inference:

* ONNX Runtime

Future compatibility:

* TensorRT support

Requirements:

* Lightweight edge models
* ONNX export pipeline
* Model optimization
* Quantization support

---

# DATABASES

Primary database:

* PostgreSQL

Caching:

* Redis

Object storage:

* R2 Cloudflare storage bucket

---

# INFRASTRUCTURE

Containerisation:

* Docker

Orchestration readiness:

* Kubernetes-compatible architecture

CI/CD:

* GitHub Actions

Monitoring:

* Prometheus
* Grafana

Reverse proxy:

* Nginx

---

# SYSTEM ARCHITECTURE REQUIREMENTS

Design a modular architecture with the following services:

* API Gateway
* Auth Service
* AI Inference Service
* Analytics Service
* Media Upload Service
* Model Registry Service
* Sync Service

The codebase MUST be organised as a monorepo.

---

# REQUIRED REPOSITORY STRUCTURE

Use this structure:

project-root/
│
├── apps/
│   ├── mobile/
│   └── web/
│
├── services/
│   ├── api-gateway/
│   ├── auth-service/
│   ├── ai-service/
│   ├── analytics-service/
│   ├── media-service/
│   ├── model-registry/
│   └── sync-service/
│
├── edge/
│   ├── mobile-inference/
│   ├── edge-runtime/
│   └── drone-sdk/
│
├── shared/
│   ├── inference-sdk/
│   ├── preprocessing/
│   ├── types/
│   └── utilities/
│
├── infrastructure/
│
├── datasets/
│
├── scripts/
│
└── docs/

---

# DATABASE REQUIREMENTS

Design production-ready schemas, including:

* users
* farms
* scans
* predictions
* diseases
* treatments
* devices
* telemetry
* model_versions
* sync_logs

Include:

* indexes
* constraints
* relationships
* migrations

Use SQLAlchemy + Alembic.

---

# API REQUIREMENTS

Design scalable REST APIs.

Examples:

* POST /auth/register
* POST /auth/login
* POST /predict
* GET /history
* GET /analytics
* POST /sync
* GET /models/latest

Requirements:

* JWT authentication
* validation
* rate limiting
* versioning
* error handling
* OpenAPI documentation

---

# AI REQUIREMENTS

Build:

* preprocessing pipeline
* augmentation pipeline
* training pipeline
* evaluation pipeline
* export pipeline

Use:

* MobileNetV3 for MVP

Requirements:

* ONNX export
* quantization support
* benchmarking
* inference optimization

The AI pipeline should support future upgrades to:

* YOLOv8
* Vision Transformers
* Segmentation models

without major rewrites.

---

# EDGE AI REQUIREMENTS

Implement:

* ONNX Runtime Mobile
* local inference engine
* inference abstraction layer
* offline prediction queue
* synchronization logic

The inference layer MUST support:

* local inference
* cloud inference
* hybrid fallback switching

---

# SECURITY REQUIREMENTS

Implement:

* JWT authentication
* password hashing
* HTTPS readiness
* secure uploads
* file validation
* API rate limiting
* RBAC authorization
* secure environment variable handling

---
---

# DEVOPS REQUIREMENTS

Include:

* Dockerfiles
* docker-compose setup
* production deployment configs
* CI/CD pipelines
* environment configurations

Provide deployment instructions for:

* local development
* staging
* production

---

# CODE QUALITY REQUIREMENTS

The entire codebase must:

* follow best practices
* be modular
* be scalable
* be maintainable
* be production-grade
* include comments
* include documentation
* include type safety
* include linting

---

# DOCUMENTATION REQUIREMENTS

Generate:

* README files
* architecture documentation
* API documentation
* deployment guides
* environment setup guides
* AI training guides
* edge deployment guides

---

# UX/UI REQUIREMENTS

Mobile app must include:

* clean agricultural-focused UI
* intuitive camera experience
* offline indicators
* sync indicators
* prediction confidence display

Web dashboard must include:

* analytics visualizations
* prediction monitoring
* admin controls
* responsive layouts

---

# DEPLOYMENT REQUIREMENTS

Provide:

* Docker deployment
* Nginx configs
* HTTPS setup
* production environment configs
* cloud deployment steps

Target environments:

* AWS
* DigitalOcean
* Ubuntu Linux servers

---

# FUTURE-READY REQUIREMENTS

The architecture MUST be designed to support future:

* drones
* UAVs
* Jetson deployment
* Raspberry Pi deployment
* real-time video detection
* autonomous agriculture systems
* telemetry ingestion
* MAVLink integrations

without architectural redesign.

---

# IMPORTANT ENGINEERING RULES

NEVER:

* tightly couple frontend and AI logic
* hardcode platform-specific inference
* build cloud-only models
* create monolithic backend logic

ALWAYS:

* use shared inference abstractions
* export ONNX models
* keep APIs universal
* separate concerns properly
* build reusable SDKs
* maintain modular architecture

---

# DELIVERABLE REQUIREMENTS

Produce:

1. Complete codebase
2. Architecture diagrams
3. Folder structure
4. Database schemas
5. Backend services
6. AI training pipeline
7. ONNX export pipeline
8. Flutter mobile app
9. Next.js dashboard
10. Shared inference SDK
11. Docker setup
12. CI/CD pipelines
13. Automated tests
14. Deployment guides
15. Environment configuration
16. Example datasets
17. API documentation
18. Build/run instructions

---

# DEVELOPMENT APPROACH

Develop the project sequentially in production-ready phases:

1. Architecture & planning
2. Infrastructure setup
3. AI pipeline
4. Backend APIs
5. Shared inference SDK
6. Mobile app
7. Web dashboard
8. Edge inference
9. Testing
10. Deployment

Each phase must include:

* explanations
* code
* tests
* setup instructions
* best practices

---

# ASSUMPTIONS

If any implementation details are unclear:

* explicitly state assumptions
* choose scalable engineering decisions
* prioritize maintainability and extensibility

---

# FINAL EXPECTATION

The final result should resemble a real enterprise-grade AI agriculture platform suitable for:

* production deployment
* startup commercialization
* investor demonstrations
* agricultural institutions
* government partnerships
* future drone/UAV expansion

The platform should be robust, scalable, maintainable, and ready for real-world agricultural environments, especially low-connectivity regions and hybrid cloud-edge deployments.
begin with the backend; create all files required, production ready; use uv as package manager