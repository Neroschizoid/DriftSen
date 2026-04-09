# 📂 DriftSentinel — Repository Map

Detailed breakdown of the project structure and the specific responsibility of every file.

## 📁 `services/` (The Application Layer)

### 🔹 `inference-service/`
- **`main.py`**: Entry point for the Prediction API. Sets up routes and model loading.
- **`api/routes.py`**: Defines `/predict`. Handles logging of features and async hand-off to Kafka.
- **`core/model_loader.py`**: Safe wrapper for loading `model.pkl` and running `model.predict()`.
- **`schemas/request_schema.py`**: Pydantic models that ensure inputs are formatted correctly as Dicts or Lists.

### 🔹 `monitoring-service/`
- **`main.py`**: Entry point for the Monitoring API (`:8001`). Starts the background consumer thread.
- **`drift_engine.py`**: **CORE LOGIC**. Implementation of the KS-Test and Z-Score statistics.
- **`sliding_window.py`**: Memory management. Implements a thread-safe circular buffer (deque) for real-time data.
- **`consumer.py`**: Logic for reading from Kafka topics or tailing the `inference.log` file.
- **`evaluator_demo.py`**: The "Final Phase" demo script for evaluators (supports normal/gradual/sudden modes).

## 📁 `ml/` (The Machine Learning Layer)
- **`models/model.pkl`**: The trained Random Forest classifier.
- **`stats/baseline_stats.json`**: The **"Source of Truth"**. Contains the mean and standard deviation for every feature from the training data.
- **`training/train.py`**: Script used to train the model and generate the baseline stats.

## 📁 `infra/` (The Infrastructure Layer)
- **`docker/Dockerfile`**: Container recipe for the Inference service.
- **`docker/Dockerfile.monitoring`**: Container recipe for the Monitoring service.
- **`docker-compose.yml`**: The orchestration file that links Inference, Monitoring, and Kafka into a single network.

## 📁 `logs/` (The Persistence Layer)
- **`inference.log`**: Every prediction made by the system is recorded here in JSON format.
- **`drift_alerts.log`**: Every time the system detects drift, it logs a "Severity" alert here for future audits.

---

## 📁 `docs/` (Documentation)
- **`architecture.md`**: System high-level design.
- **`workflow.md`**: End-to-end data lifecycle explanation.
- **`deployment_guide.md`**: Instructions for Render and Local deployment.
