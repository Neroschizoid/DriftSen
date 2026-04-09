# DriftSentinel Cloud Deployment Plan

## Goal
Deploy DriftSentinel with:
- Kafka hosted as a separate managed service.
- Inference + Monitoring services deployed as Docker web services.
- Dashboard accessible publicly from the monitoring service.

## Hosting Decision
1. Kafka: **Aiven for Apache Kafka Free Tier**.
2. Application services: **Render Free Web Services** (Docker deploy).
3. Dashboard access: served from monitoring service at `/dashboard`.

Why this stack:
- Aiven provides a no-card free Kafka tier for demos/POCs.
- Render free supports Docker web apps, which matches this repo.
- Monitoring service already serves dashboard UI and monitoring API.

## Architecture (Cloud)
1. Client/browser -> Monitoring service (`/dashboard`, `/api/v1/monitoring/*`).
2. Browser dashboard -> Inference service public URL (`/api/v1/*`).
3. Inference service -> Aiven Kafka topic `inference-events`.
4. Monitoring service -> Aiven Kafka consumer for drift detection.

## Prerequisites
1. GitHub repo connected to Render.
2. Aiven account and free Kafka service created.
3. Kafka topic `inference-events` created.
4. Aiven connection values ready:
   - `KAFKA_URL`
   - `KAFKA_SECURITY_PROTOCOL`
   - `KAFKA_SASL_MECHANISM`
   - `KAFKA_USERNAME`
   - `KAFKA_PASSWORD`
   - Any TLS file paths if required by your client profile.

## Step 1: Provision Kafka (Aiven Free Tier)
1. Create free Kafka service in Aiven Console.
2. Create topic `inference-events`.
3. Create service user and permissions for produce/consume.
4. Collect broker endpoint and auth settings.

## Step 2: Deploy Inference Service on Render (Free)
Create a Render Web Service:
1. Environment: Docker.
2. Dockerfile path: `infra/docker/Dockerfile`.
3. Start command: default from Docker image (`python3 services/inference-service/main.py`).
4. Environment variables:
   - `KAFKA_ENABLED=true`
   - `KAFKA_URL=<aiven-bootstrap-host:port>`
   - `KAFKA_SECURITY_PROTOCOL=<from-aiven>`
   - `KAFKA_SASL_MECHANISM=<from-aiven>`
   - `KAFKA_USERNAME=<from-aiven>`
   - `KAFKA_PASSWORD=<from-aiven>`
   - Optional TLS file vars if needed.
5. Health check path: `/api/v1/health`.

## Step 3: Deploy Monitoring Service on Render (Free)
Create a second Render Web Service:
1. Environment: Docker.
2. Dockerfile path: `infra/docker/Dockerfile.monitoring`.
3. Environment variables:
   - `KAFKA_ENABLED=true`
   - `KAFKA_URL=<aiven-bootstrap-host:port>`
   - `KAFKA_SECURITY_PROTOCOL=<from-aiven>`
   - `KAFKA_SASL_MECHANISM=<from-aiven>`
   - `KAFKA_USERNAME=<from-aiven>`
   - `KAFKA_PASSWORD=<from-aiven>`
   - `INFERENCE_URL=https://<inference-service>.onrender.com/api/v1`
   - `WINDOW_SIZE=100`
   - `DRIFT_EVERY_N_EVENTS=10`
   - `DRIFT_METHOD=ks`
4. Health check path: `/api/v1/monitoring/health`.

## Step 4: Dashboard Access
1. Open:
   - `https://<monitoring-service>.onrender.com/dashboard`
2. Dashboard backend APIs:
   - `https://<monitoring-service>.onrender.com/api/v1/monitoring/*`
3. Dashboard inference calls:
   - Uses `INFERENCE_URL` from monitoring config to call inference service.

## Step 5: Validation Checklist
1. Inference health returns 200.
2. Monitoring health returns 200.
3. Run sample prediction (`POST /api/v1/predict`) and check drift window updates.
4. Verify drift endpoint:
   - `GET /api/v1/monitoring/drift`
5. Open dashboard and run `normal`, `gradual`, `sudden` demo modes.

## Risks and Mitigations (Free Tier)
1. Render free spins down on idle.
   - Mitigation: expect cold starts in demo; warm both services before presentation.
2. Render free has ephemeral filesystem.
   - Mitigation: treat logs as temporary demo artifacts.
3. Aiven free tier has workload limits and idle shutdown behavior.
   - Mitigation: keep event rate low and run short demos.

## Fallback Plan
If managed Kafka setup is blocked, run monitoring in log-tail mode:
1. Set monitoring `KAFKA_ENABLED=false`.
2. Keep inference service online.
3. Demo still works, but without externally hosted Kafka in the data path.
