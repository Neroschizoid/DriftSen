# DriftSentinel – End‑to‑End Development & Deployment Summary

Below is a chronological, phase‑by‑phase recap of the work performed on the **DriftSentinel** inference service. It captures the original objectives, the concrete actions taken, the exact commands executed, the problems that surfaced, and how each was fixed. This document can serve as a reference for future contributors, auditors, or anyone needing a quick “how‑we‑got‑here” overview.

---

## Phase 1 – FastAPI Scaffold & Prediction Endpoint

| Goal | What we wanted | How we did it | Commands used | Errors / Issues | Fixes |
|------|----------------|---------------|---------------|-----------------|------|
| Create a lightweight inference API | Expose `POST /api/v1/predict` that loads a pre‑trained model once and returns `prediction`, `confidence`, and a `request_id`. | • Added `services/inference-service/main.py` with a FastAPI app and a lifespan hook. <br>• Implemented router in `services/inference-service/api/routes.py`. <br>• Added request schema (`features` can be a dict or list). | ```bash\n# Run locally for dev\nuvicorn services/inference-service/main.py:app --reload\n``` | None (initial scaffolding). | — |

**Key Files**  
- `services/inference-service/main.py` – FastAPI app with lifespan that loads model & Kafka producer.  
- `services/inference-service/api/routes.py` – `/predict` route, request validation, background logging & Kafka event production.  
- `services/inference-service/schemas/request_schema.py` – Pydantic model supporting both dict and list inputs.  

---

## Phase 2 – Structured Logging Layer

| Goal | What we wanted | How we did it | Commands used | Errors / Issues | Fixes |
|------|----------------|---------------|---------------|-----------------|------|
| Persist every request with a unique UUID, features, prediction, confidence, timestamp. | Write JSON lines to `logs/inference.log` without blocking the request. | • Added `write_log_entry` helper in `routes.py`. <br>• Used FastAPI `BackgroundTasks` to write logs asynchronously. | No explicit CLI command – just part of the code. | None. | — |

**Result** – Logs appear instantly in `logs/inference.log` and are also streamed to Kafka (next phase).  

---

## Phase 3 – Kafka Messaging Infrastructure

| Goal | What we wanted | How we did it | Commands used | Errors / Issues | Fixes |
|------|----------------|---------------|---------------|-----------------|------|
| Stream inference events (`request_id`, `features`, `prediction`, `confidence`, `timestamp`) to a Kafka topic. | Deploy a local Kafka broker via Docker‑Compose and produce messages from the API. | • Added `core/kafka_producer.py` with a singleton `KafkaProducer`. <br>• Integrated producer call in `routes.py`. | ```bash\n# Start Kafka + Inference service\ndocker compose up -d\n``` | 1. **Obsolete `version:` field** in `docker‑compose.yml`. <br>2. **Missing BuildKit / buildx** causing `docker compose build --progress=plain` failure. <br>3. **Connection refused** (`ECONNREFUSED`) when the API tried to contact Kafka before the broker was ready. | 1. Removed `version:` line from `docker‑compose.yml`. <br>2. Switched to `docker compose` (space, not dash) and installed the `docker‑buildx` plugin (`docker buildx install`). <br>3. Added retry logic (10 attempts, 2 s sleep) in `kafka_producer.get_producer`. <br>4. Added `KAFKA_ENABLED` env‑var fallback for cloud environments (see Phase 7). |

**Key Files**  
- `docker-compose.yml` – Services: `inference` (built from `infra/docker/Dockerfile`) and `kafka`.  
- `infra/docker/Dockerfile` – Python 3.10‑slim base, installs dependencies from `requirements.txt`.  
- `services/inference-service/core/kafka_producer.py` – Producer with retry & env‑var gating.  

---

## Phase 4 – API → Kafka Integration

| Goal | What we wanted | How we did it | Commands used | Errors / Issues | Fixes |
|------|----------------|---------------|---------------|-----------------|------|
| Publish an event for every prediction request. | Ensure the API does not block on Kafka, and that the message schema matches downstream consumers. | • In `routes.py`, after prediction, called `produce_inference_event`. <br>• Event includes `request_id`, `features`, `prediction`, `confidence`, `timestamp`. | No extra CLI – part of the request flow. | Initial connection errors (see Phase 3). | Resolved by retry logic and later by the `KAFKA_ENABLED` flag for Render. |

---

## Phase 5 – Dockerization & Container Orchestration

| Goal | What we wanted | How we did it | Commands used | Errors / Issues | Fixes |
|------|----------------|---------------|---------------|-----------------|------|
| Package the whole stack (FastAPI + Kafka) into Docker containers for reproducible deployment. | Build a lean image, avoid unnecessary layers, and expose port 8000. | • Created `infra/docker/Dockerfile`. <br>• Added `.dockerignore`. <br>• Updated `docker-compose.yml` to reference the Dockerfile. | ```bash\n# Build & run locally\ndocker compose up --build -d\n# Verify container status\ndocker ps\n``` | 1. **`--progress` flag** not recognized (legacy Docker). <br>2. **`version:`** line obsolete. <br>3. **Missing `apt-get`** after user removed it (no longer needed). | 1. Switched to `docker compose` (space) and removed `--progress`. <br>2. Deleted `version:` line. <br>3. Confirmed that the slim image already contains required tools; no `apt-get` needed. |

**Result** – `driftsentinel-inference-1` and `kafka` containers run side‑by‑side; API reachable at `http://localhost:8000/docs`.  

---

## Phase 6 – Pre‑Deployment Testing Suite

| Goal | What we wanted | How we did it | Commands used | Errors / Issues | Fixes |
|------|----------------|---------------|---------------|-----------------|------|
| Automate validation of API, model, logging, Kafka, edge‑cases, and performance. | One‑click script that runs all checks and reports PASS/FAIL. | • Added `tests/test_pre_deployment.py`. <br>• Uses `requests` to hit `/predict` with various payloads, checks status codes, response fields, and response time. <br>• Verifies log file contains the generated `request_id`. | ```bash\n# Run tests\npython3 -m pytest tests/test_pre_deployment.py\n# Or simply\npython3 tests/test_pre_deployment.py\n``` | None (tests passed after earlier fixes). | — |

---

## Phase 7 – GitHub Repository & Render Deployment Preparation

| Goal | What we wanted | How we did it | Commands used | Errors / Issues | Fixes |
|------|----------------|---------------|---------------|-----------------|------|
| Version‑control the project and host the Dockerized service on Render (a cloud PaaS). | Provide a clean `.gitignore`, a deployment guide, and make the code Render‑ready. | • Created a comprehensive `.gitignore` (ignores caches, logs, virtualenvs, raw data, etc.). <br>• Added `docs/deployment_guide.md` with step‑by‑step Git & Render instructions. <br>• Implemented a **health‑check endpoint** (`/api/v1/health`). <br>• Modified `main.py` to read `PORT` env‑var and disable reload in production. <br>• Added `KAFKA_ENABLED` env‑var gating in `kafka_producer.py`. | ```bash\n# Initialise repo (if not already)\ngit init\ngit add .\ngit commit -m "Initial commit"\n# Push to GitHub\ngit remote add origin https://github.com/<user>/DriftSentinel.git\ngit branch -M main\ngit push -u origin main\n``` | 1. **Render UI defaulted to “Python 3”** – would ignore our Dockerfile. <br>2. **Missing environment variables** (Kafka would fail). | 1. In Render, set **Language → Docker**. <br>2. Add `KAFKA_ENABLED=false` and `PORT=8000` in the Environment Variables section. <br>3. Set **Health Check Path → /api/v1/health**. |

**Result** – All required Render settings are documented and ready to be applied.  

---

## Phase  8 – Monitoring Service & Drift Detection (Week 2 Core)

| Goal | What we wanted | How we did it | Commands used | Errors / Issues | Fixes |
|------|----------------|---------------|---------------|-----------------|------|
| Implement real-time drift detection and alerting. | Consume logs/Kafka events and compare live distributions against training baseline via KS-test. | • Added `services/monitoring-service` with background consumer. <br>• Created `DriftEngine` with KS-test logic and `SlidingWindow` buffer. <br>• Implemented native severity classification (LOW/MEDIUM/HIGH). | ```bash\n# Run docker-unified stack\ndocker compose up --build -d\n``` | 1. **KS-Test Sensitivity**: Initial threshold (0.1) triggered false positives on 10 samples. <br>2. **Demo Insight**: Gradual drift was missed by wide thresholds. | 1. Adjusted `KS_THRESHOLD` to 0.3. <br>2. Implemented `evaluator_demo.py` with adaptive scenarios. <br>3. Relocated severity logic into core `drift_engine`. |

**Key Files**  
- `services/monitoring-service/main.py` – Fast API monitor with background consumer.
- `services/monitoring-service/drift_engine.py` – Statistical brain (KS-Test + Severity).
- `services/monitoring-service/sliding_window.py` – Thread-safe FIFO feature buffer.

---

## Phase  9 – “Level 2” Evaluator Demo & Polish

| Goal | What we wanted | How we did it | Commands used | Errors / Issues | Fixes |
|------|----------------|---------------|---------------|-----------------|------|
| Prove the system works in realistic scenarios. | Create a script that simulates Normal, Gradual, and Sudden drift patterns through the API. | • Added `evaluator_demo.py` with multi-mode support. <br>• Integrated latency tracking (ms) per request. <br>• Added professional system-status messages. | ```bash\npython services/monitoring-service/evaluator_demo.py --mode gradual\n``` | 1. **Artificial Drift**: The first simulation felt scripted. | 1. Rebuilt generator to use statistical noise (std x1.0) and gradual drift multipliers. |

---

## Phase  10 – System Finalizing & Documentation (COMPLETE)

- **Inference API** works via Swagger UI (`/docs`).  
- **Monitoring API** live at `:8001/api/v1/monitoring/drift`.
- **KS-Test** correctly identifies distribution shifts using training baseline.
- **Severity Classifier** (LOW/MED/HIGH) implemented and verified.
- **Latency Tracking** integrated into demo outputs.
- **Docker Compose** orchestrates Inf + Mon + Kafka seamlessly.
- **Gradual/Sudden Drift** patterns supported in `evaluator_demo.py`.
- **Pre‑deployment tests** and **Live Demo script** all pass.
- **Architecture & Workflow Documentation** finalized.

---

### How to Use This Summary
1. **Read** the sections relevant to your current task (e.g., if you’re debugging Monitoring, see Phase 8).  
2. **Copy** any command you need from the “Commands used” column.  
3. **Follow** the “Fixes” bullet points if you encounter historical errors.  

---

*Prepared by Antigravity — The MLOps Watchdog.*
