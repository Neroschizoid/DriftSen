# DriftSentinel Complete Project Explanation

This document is a full, from-scratch walkthrough of DriftSentinel assuming the reader starts with zero context. It explains the purpose, architecture, runtime workflow, tech stack, codebase structure, file-by-file roles, known difficulties, fixes, and how all parts connect.

## 1) What DriftSentinel Is

DriftSentinel is an MLOps system for network intrusion detection that does two things at once:

1. Serve predictions through a low-latency inference API.
2. Continuously monitor incoming prediction traffic for data drift.

The core engineering idea is **decoupling**:

1. The inference service should stay fast and return responses immediately.
2. Drift detection can be heavier, so it runs asynchronously in a separate monitoring service.

## 2) Why This Exists (Problem Statement)

A model that performs well on training/test data can degrade in production when live data shifts. This shift is called **data drift**.

If drift is not monitored:

1. Predictions can become unreliable without obvious failures.
2. Teams only discover issues after business impact.
3. Retraining decisions become reactive and late.

DriftSentinel addresses this by making drift observable and actionable in near real-time.

## 3) End-to-End Runtime Workflow

### Step A: Client Prediction Request

1. A client sends `POST /api/v1/predict` to the inference service.
2. The request payload contains `features`, either as:
1. a feature dictionary, or
2. a numeric list.

### Step B: Inference Path (Fast)

1. Inference service loads `ml/models/model.pkl` once at startup.
2. Input is transformed to the model feature schema.
3. Prediction and confidence are computed.
4. Response is returned immediately to the caller.

### Step C: Event Capture

After returning the API response, inference schedules a background task to:

1. Append the event to `logs/inference.log` (JSON line).
2. Publish the same event to Kafka topic `inference-events` when Kafka is enabled.

### Step D: Monitoring Path (Async)

Monitoring service runs a background consumer thread that reads events either from:

1. Kafka (`KAFKA_ENABLED=true`), or
2. Log tail fallback (`KAFKA_ENABLED=false`).

It validates events, pushes them into a sliding window, and every N events (`DRIFT_EVERY_N_EVENTS`, default 10) computes drift.

### Step E: Drift Computation

1. DriftEngine loads baseline stats from `ml/stats/baseline_stats.json`.
2. For each feature in the live window, it runs KS-test (default) or z-score method.
3. It counts drifted features and computes:
1. `drift_score = features_drifted / features_checked`
2. `drift_detected = drift_score >= DRIFT_FEATURE_RATIO` (default 0.3)
3. `drift_severity` tier: LOW, MEDIUM, HIGH.

### Step F: Alerting and Observability

1. Latest drift result is stored in memory for API reads.
2. If drift is detected, an alert JSON record is appended to `logs/drift_alerts.log`.
3. Dashboard reads monitoring APIs and shows trend, gauge, heatmap, latency, and demo logs.

## 4) Tech Stack

### Backend

1. Python 3.10
2. FastAPI (inference + monitoring HTTP APIs)
3. Uvicorn (ASGI server)
4. Pydantic (request schema validation)

### ML and Statistics

1. scikit-learn (RandomForest model)
2. pandas, numpy (preprocessing and numeric operations)
3. scipy (KS statistical test)
4. joblib (model persistence)

### Streaming and Infra

1. kafka-python (producer/consumer)
2. Docker and Docker Compose
3. Confluent Kafka image (`cp-kafka:7.8.0`)

### Testing and CI

1. pytest
2. requests (integration tests)
3. GitHub Actions CI (`.github/workflows/ci.yml`)

### Frontend Dashboard

1. HTML/CSS/JavaScript (served by monitoring service)
2. Chart.js for drift trend visualization

## 5) Directory and File-by-File Breakdown

This section maps every major file to its role in the system.

---

## 5.1 Root-Level Runtime and Config

### `docker-compose.yml`

Defines 3 services:

1. `inference`
2. `monitoring`
3. `kafka`

Key design points:

1. Inference has `KAFKA_ENABLED=true` and sends to internal `kafka:9092`.
2. Monitoring defaults to `KAFKA_ENABLED=false` to support log-tail fallback.
3. Kafka uses dual listeners:
1. container network listener (`kafka:9092`)
2. host listener (`localhost:29092`) for host-side tests.

### `requirements.txt`

Pinned runtime dependencies for app, stats, tests, and Kafka.

### `pytest.ini`

Configures pytest to:

1. discover tests in `tests/`
2. register `integration` marker
3. run only non-integration tests by default (`-m "not integration"`).

### `README.md`

Current top-level usage doc with:

1. architecture summary
2. train/run instructions
3. test instructions
4. dashboard entrypoint.

### `.github/workflows/ci.yml`

CI pipeline that:

1. checks out code
2. installs dependencies
3. runs unit tests (`python -m pytest -q`).

---

## 5.2 Documentation Folder (`docs/`)

### `docs/architecture.md`

Conceptual high-level architecture and decoupling narrative.

### `docs/workflow.md`

Narrative request-to-alert flow explanation.

### `docs/repository_map.md`

Human-readable map of module responsibilities.

### `docs/project.md`

Chronological development history and phase tracking.

### `docs/deployment_guide.md`

Practical local deployment and test commands.

### `docs/difficulty.md`

Critical engineering issue log (errors, causes, fixes).

### `docs/presentation_storyline.md`

Presentation narrative (problem -> solution -> architecture -> demo -> validation -> impact -> next steps).

### `docs/WEEK1_TRACKER.md`

Early checklist stub for backend architecture and ML automation.

---

## 5.3 Inference Service (`services/inference-service/`)

### `services/inference-service/main.py`

Role:

1. creates FastAPI app
2. startup lifecycle loads model and Kafka producer
3. logs startup state (`kafka_enabled`, URL, connection state)
4. applies permissive CORS for dashboard cross-port calls.

### `services/inference-service/api/routes.py`

Role:

1. `GET /health` for service readiness
2. `POST /predict` for inference
3. asynchronous `BackgroundTasks` logging and Kafka event publish.

Important behavior:

1. API response returns quickly.
2. Log + Kafka happen in background function `write_log_entry`.

### `services/inference-service/core/model_loader.py`

Role:

1. load `ml/models/model.pkl`
2. keep model and feature names in memory
3. normalize input formats:
1. list inputs are padded/sliced to model feature count
2. dict inputs are one-hot encoded and reindexed to training schema.

### `services/inference-service/core/kafka_producer.py`

Role:

1. build and cache singleton producer
2. enforce `KAFKA_ENABLED` gating
3. retry connection attempts during startup races
4. publish inference events with broker acknowledgment:
1. `producer.send(...).get(timeout=5)`.

### `services/inference-service/schemas/request_schema.py`

Defines request model:

1. `features: Union[Dict[str, Any], List[float]]`.

### `services/inference-service/utils/logger.py`

Simple service-level logger setup.

---

## 5.4 Monitoring Service (`services/monitoring-service/`)

### `services/monitoring-service/main.py`

This is the most important orchestration module.

It provides:

1. background consumer loop (Kafka or log tail)
2. drift compute cadence
3. alert logging
4. dashboard serving (`/dashboard`, static assets)
5. monitoring APIs (`health`, `config`, `window`, `drift`)
6. demo orchestration APIs:
1. run/stop drift scenarios
2. run runbook commands (health check, sample inference, show drift, show logs, unit tests, Kafka test, shutdown attempt)
3. expose live demo status + logs for UI.

It also includes state reset endpoint:

1. `POST /api/v1/monitoring/reset_state`
2. clears sliding window
3. clears latest drift state
4. clears demo log stream.

### `services/monitoring-service/drift_engine.py`

Implements per-feature statistical drift detection.

Methods:

1. z-score drift (`_zscore_drift`)
2. KS-test drift (`_ks_drift`, default)

Outputs:

1. per-feature report
2. global drift score and boolean
3. severity classification.

Threshold controls via env vars:

1. `DRIFT_ZSCORE_THRESHOLD` (default 3.0)
2. `DRIFT_KS_THRESHOLD` (default 0.3)
3. `DRIFT_FEATURE_RATIO` (default 0.3).

### `services/monitoring-service/sliding_window.py`

Thread-safe FIFO event buffer.

Key behavior:

1. fixed max size (`deque(maxlen=...)`)
2. auto-eviction of oldest events
3. thread-safe read/write via lock
4. helper methods for `features`, `summary`, and `clear`.

### `services/monitoring-service/drift_state.py`

In-memory shared state for latest drift result.

Functions:

1. `store(result)` adds `computed_at`
2. `load()` returns copy
3. `clear()` resets state.

### `services/monitoring-service/consumer.py`

Older standalone consumer script for local debugging.

Role:

1. consume Kafka or tail logs
2. validate events
3. print stream summaries.

### `services/monitoring-service/evaluator_demo.py`

CLI demo runner for `normal | gradual | sudden` scenarios.

Outputs per-iteration lines in this style:

1. latency in ms
2. current drift score
3. severity state.

### `services/monitoring-service/simulate_drift.py`

Alternative log-file simulator that writes synthetic normal/drifted events and checks monitor endpoint.

---

## 5.5 Dashboard Frontend

### `services/monitoring-service/dashboard/index.html`

Dashboard layout with:

1. left control panel
2. runbook shortcut buttons
3. drift trend chart
4. severity gauge
5. latency card
6. heatmap card
7. live command/demo log stream.

### `services/monitoring-service/dashboard/static/app.js`

Browser controller logic.

Responsibilities:

1. pull monitoring snapshots
2. render trend/gauge/heatmap/KPIs
3. run demo modes through backend APIs
4. execute runbook shortcut commands
5. poll and render backend demo logs.

### `services/monitoring-service/dashboard/static/styles.css`

Dashboard visual theme and responsive layout.

---

## 5.6 ML Layer (`ml/`)

### `ml/models/model.pkl`

Serialized trained RandomForest model artifact.

### `ml/stats/baseline_stats.json`

Baseline statistics used by drift engine.

Current observed characteristics:

1. 190 feature entries
2. each contains `mean` and `std`.

### `ml/training/data_validation.py`

Validation utilities for raw dataset quality and schema checks.

### `ml/training/data_preprocessing.py`

Preprocessing pipeline:

1. drops `id`, `attack_cat`
2. separates target label
3. one-hot encodes categorical features
4. enforces numeric, finite values
5. computes baseline stats.

### `ml/training/train.py`

Training pipeline:

1. validate dataset
2. preprocess features
3. split train/test
4. train RandomForest
5. compute metrics
6. save `model.pkl`
7. save `baseline_stats.json`.

---

## 5.7 Test Suite (`tests/`)

### `tests/test_training_pipeline_unit.py`

Unit tests for:

1. dataframe validation
2. preprocessing behavior
3. baseline stats output structure.

### `tests/test_monitoring_unit.py`

Unit tests for:

1. sliding-window eviction
2. empty-window drift behavior
3. non-empty feature report behavior.

### `tests/test_pre_deployment.py`

Integration tests for running inference API.

Covers:

1. health readiness wait
2. valid prediction requests
3. invalid payload rejection
4. basic throughput target.

### `tests/test_kafka_integration.py`

Integration test for API -> Kafka event path.

Flow:

1. send prediction with unique marker
2. consume from topic
3. assert marker event is observed.

---

## 5.8 Infra Helpers

### `infra/docker/Dockerfile`

Inference service container build file.

### `infra/docker/Dockerfile.monitoring`

Monitoring service container build file.

### `infra/scripts/run.sh`

Simple helper shell script stub.

### `infra/kafka/setup.md`

Placeholder note for Kafka setup instructions.

## 6) Design Decisions and Why They Matter

### Decoupled Inference and Monitoring

Why:

1. protect user-facing latency
2. let drift computation evolve independently
3. isolate failures (monitor issues should not kill prediction path).

### Dual Event Path: Log + Kafka

Why:

1. log path gives local simplicity and replay capability
2. Kafka path gives scalable event streaming
3. fallback mode increases resilience.

### Sliding Window Monitoring

Why:

1. bounded memory
2. drift based on recent behavior
3. suited for ongoing streams.

### Statistical Drift Thresholding

Why:

1. avoid binary magic triggers
2. score and severity communicate risk levels to operators.

### Dashboard + Orchestrator

Why:

1. operational observability
2. demo reproducibility
3. no constant terminal context switching.

## 7) Environment Variables and Runtime Controls

Important variables:

1. `KAFKA_ENABLED`
2. `KAFKA_URL`
3. `WINDOW_SIZE`
4. `DRIFT_EVERY_N_EVENTS`
5. `DRIFT_METHOD`
6. `DRIFT_KS_THRESHOLD`
7. `DRIFT_FEATURE_RATIO`
8. `INFERENCE_URL` (monitoring-side call target).

## 8) Known Difficulties Encountered (From `docs/difficulty.md`) and Fixes

This section mirrors the official difficulty log and explains effect on system behavior.

### 8.1 Compose Version and Build Tooling Issues

Problem:

1. Compose version tag mismatch warnings/errors
2. buildx/plugin inconsistency.

Fix:

1. removed legacy `version:` usage
2. standardized compose/build usage.

Impact:

1. predictable local builds across environments.

### 8.2 Kafka Startup Race (`ECONNREFUSED`)

Problem:

1. inference starts before Kafka is ready.

Fix:

1. retry loop in producer connection setup.

Impact:

1. fewer startup crashes, smoother container boot.

### 8.3 Host vs Container Kafka Connectivity

Problem:

1. host-side tests/scripts could not consume from broker with internal-only listener.

Fix:

1. dual listeners (`9092` internal + `29092` host).

Impact:

1. integration tests and host tooling now work consistently.

### 8.4 Flaky Event Visibility in Tests

Problem:

1. fire-and-forget Kafka send caused timing races.

Fix:

1. wait for broker ack (`send().get(timeout=5)`).

Impact:

1. deterministic test behavior and stronger delivery guarantee.

### 8.5 Drift Over-Sensitivity (False Positives)

Problem:

1. KS threshold too low, causing drift alerts even for near-normal data.

Fix:

1. tuned KS threshold to `0.3`.

Impact:

1. better precision vs sensitivity balance.

### 8.6 Numpy Boolean JSON Serialization

Problem:

1. `numpy.bool_` not serializable with stdlib JSON.

Fix:

1. cast to native `bool`.

Impact:

1. stable API/log serialization paths.

### 8.7 Simulation Calibration

Problem:

1. unrealistic low-noise synthetic generation made drift detection unstable.

Fix:

1. increased realistic gaussian variability.

Impact:

1. scenario demos reflect real distributions better.

### 8.8 Env-Visibility and Debuggability

Problem:

1. missing startup observability around env toggles.

Fix:

1. explicit inference startup logs for Kafka mode and connection status.

Impact:

1. faster diagnosis of config/runtime mismatches.

## 9) Operational Runbook (How Components Work Together in Practice)

1. Start stack with Docker compose.
2. Inference starts, loads model, attempts Kafka producer init.
3. Monitoring starts consumer thread and awaits events.
4. User/demo traffic hits inference `/predict`.
5. Events are logged and optionally streamed.
6. Monitoring receives events, updates window, computes drift every N events.
7. Dashboard pulls state APIs and renders trend + severity + feature-level details.
8. If drift detected, alert log is appended.

## 10) Why Drift Severity May Stay High for a While

This was a practical issue observed during demos.

Behavioral reason:

1. drift result reflects recent window history
2. once many drifted events fill window, score remains high until enough normal events replace them.

Mitigation added:

1. reset endpoint clears window + drift state
2. scenario generator now uses full baseline-feature sampling.

## 11) Current Strengths

1. clear service separation
2. robust local deployment with Kafka + fallback mode
3. statistical drift detection with feature-level reporting
4. dashboard with scenario orchestration and command logs
5. unit + integration testing paths
6. CI baseline in place.

## 12) Current Gaps / Improvement Opportunities

1. no persistent historical drift DB yet
2. command-driven shutdown from monitoring can be environment-limited
3. no automatic retraining pipeline yet
4. auth/role-based controls not implemented
5. richer production alert channels (email/slack/webhooks) pending.

## 13) If You Need to Understand It Fast (Learning Sequence)

Recommended read order:

1. `README.md`
2. `docker-compose.yml`
3. inference service files
4. `services/monitoring-service/main.py`
5. `drift_engine.py`, `sliding_window.py`, `drift_state.py`
6. dashboard files
7. tests
8. `docs/difficulty.md`.

## 14) Summary

DriftSentinel is a practical MLOps platform that demonstrates:

1. production-style decoupled inference and monitoring
2. event-driven drift detection
3. observable, testable, and demo-friendly operations
4. iterative engineering maturity through explicit issue tracking and fixes.

If you understand each section above, you understand the full project lifecycle from data input to live drift alerting.
