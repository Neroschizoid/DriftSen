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
