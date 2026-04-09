# 📝 DriftSentinel — Technical Difficulty Log

This document records the engineering challenges, bugs, and architectural shifts encountered during the development of the DriftSentinel platform.

---

## 🏗️ 1. Docker & Infrastructure

### ❌ Issue: `docker-compose.yml` Version Mismatch
- **Error**: Compose file rejected due to the `version: 'x'` line.
- **Why it happened**: Recent versions of Docker Compose have deprecated the mandatory version tag. Using it on modern engines can cause parsing warnings or errors depending on the plugin version.
- **Resolution**: Removed the `version:` line from the root of `docker-compose.yml` to ensure compatibility with modern Compose V2.

### ❌ Issue: Build Failures (Missing Buildx)
- **Error**: `docker compose build` failed to recognize build instructions or progress flags.
- **Why it happened**: The environment was missing the Docker `buildx` plugin, which is required for advanced build features in modern Compose.
- **Resolution**: Prompted the user to install/verify BuildKit/buildx and switched to standard `docker compose build` syntax.

---

## 📡 2. Real-Time Data Streaming (Kafka)

### ❌ Issue: Connection Refused (`ECONNREFUSED`)
- **Error**: The Inference Service container would crash on startup because it couldn't find Kafka.
- **Why it happened**: A race condition. The FastAPI container starts faster than the Kafka broker.
- **Resolution**: Added a robust retry mechanism in `core/kafka_producer.py` that attempts to connect 10 times with a 2-second sleep between attempts.

### ❌ Issue: Host-to-Container Connectivity
- **Error**: Scripts running on the host (like `evaluator_demo.py`) could not connect to `localhost:9092`.
- **Why it happened**: Kafka was only advertising its internal container name (`kafka:9092`). External host machines did not have a mapping for that name.
- **Resolution**: Implemented **Dual Listeners** in `docker-compose.yml`:
    - `PLAINTEXT`: For container-to-container communication (9092).
    - `PLAINTEXT_HOST`: For host-to-container communication (29092).

### ❌ Issue: Flaky Test Events (Fire-and-Forget)
- **Error**: Events weren't appearing in the monitor fast enough for tests to catch them.
- **Why it happened**: The Kafka producer was sending messages asynchronously without waiting for an acknowledgement.
- **Resolution**: Added `.get(timeout=5)` to the `producer.send()` call in `kafka_producer.py` to ensure the broker actually received the event before the code continued.

---

## 📊 3. Drift Detection & Statistics

### ❌ Issue: KS-Test Over-Sensitivity
- **Error**: Drift was detected even on "Normal" data.
- **Why it happened**: The threshold was set to `0.1`. In small window sizes (100 samples), natural statistical variance can easily exceed 0.1, causing false positives.
- **Resolution**: Tuned `KS_THRESHOLD` to `0.3` after running multiple simulations to find the optimal balance between sensitivity and stability.

### ❌ Issue: JSON Serialization Failure (`numpy.bool_`)
- **Error**: `TypeError: Object of type bool_ is not JSON serializable`.
- **Why it happened**: Scipy/Numpy return their own boolean types (e.g., `numpy.bool_`). The standard Python `json` library cannot serialize these directly.
- **Resolution**: Explicitly cast the drift result to native Python types: `bool(ks_stat > KS_THRESHOLD)`.

### ❌ Issue: Simulation Noise Calibration
- **Error**: `simulate_drift.py` triggered drift too easily even in normal mode.
- **Why it happened**: Initial feature generation used a gaussian noise of `0.05`, which was too narrow, making individual samples "too similar" and causing any slight shift to look like significant drift.
- **Resolution**: Increased Gaussian noise multiplier to `1.0` to better reflect real-world variability.

---

## 🛠️ 4. API & Environment

### ❌ Issue: Invisible Environment Variables
- **Error**: `KAFKA_ENABLED` or `PORT` were not acting as expected inside containers.
- **Why it happened**: Lack of observability during the "lifespan" startup phase.
- **Resolution**: Added detailed startup logging in `main.py` using a dedicated logger to print the state of all critical environment variables on container launch.

---

*Prepared by Antigravity — Recorded on 2026-04-09*
