# DriftSentinel Deployment Guide

## Local Docker Deployment

```bash
docker compose up --build -d
docker compose ps
```

Endpoints:
- Inference API: `http://localhost:8000/api/v1/health`
- Monitoring API: `http://localhost:8001/api/v1/monitoring/health`
- Kafka host listener: `localhost:29092`

## Required Runtime Variables

Inference:
- `KAFKA_ENABLED=true` to publish events to Kafka
- `KAFKA_URL=kafka:9092` for container-to-container networking

Monitoring:
- `KAFKA_ENABLED=false` for log-tail mode or `true` for Kafka mode
- `KAFKA_URL=kafka:9092`
- `WINDOW_SIZE=100`
- `DRIFT_EVERY_N_EVENTS=10`
- `DRIFT_METHOD=ks`

## Train/Refresh Baseline Artifacts

```bash
python3 ml/training/train.py \
  --csv-path data/raw/UNSW_NB15_training-set.csv \
  --model-out ml/models/model.pkl \
  --stats-out ml/stats/baseline_stats.json
```

## Test Commands

Unit tests:
```bash
python3 -m pytest -q
```

API integration (opt-in):
```bash
RUN_API_INTEGRATION=true python3 -m pytest -q tests/test_pre_deployment.py -m integration
```

Kafka integration (opt-in):
```bash
RUN_KAFKA_INTEGRATION=true \
KAFKA_BOOTSTRAP_SERVERS=localhost:29092 \
python3 -m pytest -q tests/test_kafka_integration.py -m integration
```
