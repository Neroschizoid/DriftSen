# DriftSentinel Storyline (Gamma-Ready)

## Problem
Modern ML systems fail silently when live data changes over time. A model that works during training can degrade in production due to data drift, leading to unreliable predictions and delayed response. Most inference APIs focus only on speed and accuracy at request time, but they do not provide continuous post-deployment visibility into data quality shifts.

## Solution
DriftSentinel solves this by combining low-latency inference with asynchronous drift monitoring.

- Inference remains fast and isolated.
- Every prediction event is captured for monitoring.
- A dedicated monitoring service computes drift continuously using statistical checks.
- Drift is classified into severity levels (LOW, MEDIUM, HIGH).
- A live dashboard exposes trend, severity, feature-level drift, and latency in one place.

## Architecture
DriftSentinel uses a decoupled two-service architecture:

1. **Inference Service (FastAPI)**
- Serves `POST /predict`.
- Loads trained model artifact (`ml/models/model.pkl`).
- Returns prediction + confidence quickly.
- Writes events to `logs/inference.log`.
- Publishes events to Kafka when enabled.

2. **Monitoring Service (FastAPI + background consumer)**
- Consumes inference events from Kafka or tails inference logs (fallback mode).
- Maintains a fixed-size sliding window of recent events.
- Computes drift every `N` events using KS test (with z-score support).
- Stores latest drift state and writes drift alerts to `logs/drift_alerts.log`.
- Serves dashboard and orchestration endpoints.

3. **Dashboard Layer**
- Visualizes drift trend, severity gauge, feature heatmap, and latency tracker.
- Includes one-click runbook actions for demo steps.
- Supports mode-based traffic simulation (normal, gradual, sudden).

## Folder Roles (Talk Track)
Use this as a quick presenter script when walking through the repo:

1. **`services/` -> Runtime application layer**
- `inference-service/`: serves predictions and emits monitoring events.
- `monitoring-service/`: consumes events, computes drift, serves dashboard APIs/UI.

2. **`ml/` -> Model and statistical baseline layer**
- `models/`: trained model artifact used by inference.
- `stats/`: training-time baseline statistics for drift comparison.
- `training/`: scripts for preprocessing, validation, and retraining.

3. **`infra/` -> Deployment and orchestration layer**
- `docker/`: service container definitions.
- `kafka/`: messaging setup notes.
- root `docker-compose.yml`: local full-stack wiring.

4. **`tests/` -> Quality and confidence layer**
- Unit and integration checks for inference, monitoring, and Kafka flow.

5. **`docs/` -> Project communication layer**
- Architecture, workflow, deployment, evaluation trackers, and this storyline.

6. **Root files -> Project control layer**
- `README.md`: entrypoint for setup and usage.
- `requirements.txt`: dependency lock for Python services.
- `pytest.ini`: shared test configuration.

## Role Demo Q&A (Question + Answer)
Use this section for role-wise demo speaking prompts.

1. **ML Engineer**
- Question: Where does the model and baseline come from?
- Answer: The model is loaded from `ml/models/model.pkl`, and baseline feature distributions come from `ml/stats/baseline_stats.json`, generated from training data.
- Question: Why do we compare live data with training-time stats?
- Answer: Drift means live inputs no longer match what the model learned on, so training baselines are the reference point for detecting reliability risk.
- Question: What should we expect in Normal, Gradual, and Sudden modes?
- Answer: Normal stays near stable drift scores, Gradual rises slowly over time, and Sudden jumps quickly to high-severity drift.

2. **Backend / Inference Engineer**
- Question: What happens when a request hits `POST /predict`?
- Answer: Input is validated, the model predicts class/confidence, the response is returned quickly, and the event is logged and published for monitoring.
- Question: How do we keep inference fast while still monitoring?
- Answer: Monitoring is asynchronous through logs/Kafka, so drift checks do not block prediction response time.
- Question: Where is inference evidence stored?
- Answer: Prediction events are written to `logs/inference.log` and can also flow through Kafka for downstream monitoring.

3. **Monitoring Engineer**
- Question: How does monitoring ingest events?
- Answer: It consumes from Kafka first, and can fall back to log-tail mode from inference logs if needed.
- Question: How is drift computed in practice?
- Answer: Recent events are kept in a sliding window, then statistical checks (KS test, with z-score support) run every configured interval.
- Question: How do severity levels work?
- Answer: Drift score thresholds map to NONE/LOW/MEDIUM/HIGH and high-confidence drift states are logged as alerts.

4. **DevOps / Infra Engineer**
- Question: What components are running in this stack?
- Answer: `docker-compose.yml` wires inference service, monitoring service, Kafka, and supporting runtime dependencies into one local environment.
- Question: What should be verified before demo execution?
- Answer: Service health endpoints, Kafka availability, and log paths should all be healthy before running traffic simulation modes.
- Question: What is our audit trail during demo?
- Answer: `logs/inference.log` and `logs/drift_alerts.log` are the primary traceable artifacts used as operational evidence.

5. **QA / Test Engineer**
- Question: How is quality validated?
- Answer: Unit tests verify core logic, integration tests verify service contracts and Kafka flow, and operational checks verify health/drift/log outputs.
- Question: Which demo claims are test-backed?
- Answer: API behavior, payload handling, drift primitives, and Kafka event path are test-backed; live drift visualization is demonstrated at runtime.
- Question: What limitation should we disclose?
- Answer: Historical long-term drift persistence and full automation loops (like auto-retraining) are roadmap items, not fully productionized yet.

6. **Presenter / Product Owner**
- Question: What is the one-line project story?
- Answer: DriftSentinel detects silent ML degradation early by combining fast inference with continuous, real-time drift monitoring.
- Question: What business value should be emphasized?
- Answer: Faster detection of model risk, better auditability, and improved trust in predictions for operational decision-making.
- Question: How should we close the demo?
- Answer: Summarize proof points (API response, severity change, logs, tests) and then tie roadmap items to scale and governance outcomes.

## Demo
The demo is designed to run fully from dashboard controls (minimal terminal dependence).

### Core demo sequence
1. Verify inference and monitoring health.
2. Trigger sample inference and show response.
3. Run **Normal** mode to show stable behavior.
4. Run **Gradual** mode to show drift score rise over time.
5. Run **Sudden** mode to show rapid jump to high severity.
6. Show drift endpoint output and live logs.
7. Show audit evidence from inference and drift alert logs.
8. Trigger test commands (unit/Kafka integration) and show outcomes.

### What audience sees
- Drift trend line changes over time.
- Severity gauge transitions across NONE/LOW/MEDIUM/HIGH.
- Feature heatmap highlights out-of-bounds features.
- Latency ticker shows live inference response times.
- Command log panel captures each step with traceable outputs.

## Validation
Validation is performed at multiple levels:

1. **Unit tests**
- Training data validation and preprocessing logic.
- Monitoring primitives (sliding window and drift engine behavior).

2. **Integration tests**
- Inference endpoint behavior and payload validation.
- Kafka pipeline verification (`/predict` event appears in Kafka topic).

3. **Operational validation**
- Health endpoints.
- Drift endpoint checks.
- Log/audit verification (`inference.log`, `drift_alerts.log`).

4. **CI validation**
- Unit tests run automatically via CI workflow on push/PR.

## Impact
DriftSentinel demonstrates a production-minded ML monitoring pattern:

- Keeps prediction path fast while running heavy checks asynchronously.
- Provides real-time drift observability instead of delayed manual audits.
- Improves trust with feature-level explanations and severity signals.
- Enables repeatable demos and evaluations with one-click orchestration.
- Reduces operational risk from silent model degradation.

## Next Steps
1. Add persistent historical drift storage for long-term analytics.
2. Add auto-retraining triggers based on drift thresholds.
3. Introduce role-based dashboard access and alert channels (email/Slack/webhook).
4. Extend from single-model to multi-model monitoring.
5. Deploy with managed Kafka and cloud-native observability stack.
