# DriftSentinel

DriftSentinel is a real-time MLOps project for intrusion detection with:
- FastAPI inference service
- Kafka/log-based event streaming
- Monitoring service with sliding-window drift detection
- Alert logging and demo drift simulations

## Architecture

1. Client calls `POST /api/v1/predict`.
2. Inference predicts using `ml/models/model.pkl`.
3. Inference writes structured events to `logs/inference.log`.
4. Inference publishes events to Kafka topic `inference-events` (when enabled).
5. Monitoring consumes Kafka or tails logs, updates a sliding window, and computes drift.
6. Drift alerts are written to `logs/drift_alerts.log`.

## Repository Layout

- `services/inference-service`: Prediction API, model loading, Kafka producer.
- `services/monitoring-service`: Consumer loop, drift engine, monitoring API.
- `ml/training`: Dataset validation, preprocessing, training pipeline.
- `ml/models/model.pkl`: Trained baseline model artifact.
- `ml/stats/baseline_stats.json`: Baseline feature statistics for drift checks.
- `tests`: Unit and integration tests.
- `infra/docker`: Service Dockerfiles.
- `docker-compose.yml`: Local orchestration for inference, monitoring, and Kafka.

## Prerequisites

- Python `3.10`
- Docker + Docker Compose

## Install

```bash
pip install -r requirements.txt
```

## Dataset

Place the UNSW-NB15 CSV at:

```text
data/raw/UNSW_NB15_training-set.csv
```

## Train Baseline Model

This command validates the dataset, preprocesses features, trains a `RandomForestClassifier`, and writes artifacts:

```bash
python3 ml/training/train.py \
  --csv-path data/raw/UNSW_NB15_training-set.csv \
  --model-out ml/models/model.pkl \
  --stats-out ml/stats/baseline_stats.json
```

## Run Locally (Docker)

```bash
docker compose up --build -d
```

Services:
- Inference API: `http://localhost:8000/docs`
- Monitoring API: `http://localhost:8001/docs`
- Live dashboard: `http://localhost:8001/dashboard`
- Kafka host listener for tests: `localhost:29092`

## Testing

### Unit tests (default)

`pytest.ini` is configured to run only non-integration tests by default.

```bash
python3 -m pytest -q
```

### Integration tests (opt-in)

1. API integration tests:
```bash
RUN_API_INTEGRATION=true python3 -m pytest -q tests/test_pre_deployment.py -m integration
```

2. Kafka end-to-end test:
```bash
RUN_KAFKA_INTEGRATION=true \
KAFKA_BOOTSTRAP_SERVERS=localhost:29092 \
python3 -m pytest -q tests/test_kafka_integration.py -m integration
```

## Monitoring and Drift Demo

Run evaluator demo after services are up:

```bash
python3 services/monitoring-service/evaluator_demo.py --mode gradual
```

Modes:
- `normal`
- `gradual`
- `sudden`

Dashboard includes one-click controls for:
- mode-based simulation (`normal`, `gradual`, `sudden`)
- custom feature payload prediction
- live drift/latency/feature visualisation

## CI

GitHub Actions workflow:
- `.github/workflows/ci.yml`
- Installs dependencies and runs unit tests on push and pull request.
