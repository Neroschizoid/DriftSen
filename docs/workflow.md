# 🔄 DriftSentinel — System Workflow

This guide follows a single piece of data from the user interface all the way to a "Drift Detected" alert.

## 1. The Interaction (User -> Inference)
When a user sends a request to `POST /predict`:
- The **Inference Service** validates the input using Pydantic.
- It calculates a prediction (0 or 1) and a confidence score.
- **Critical Action**: It triggers an "asynchronous background task" to log the event. This prevents the user from waiting while the system writes to logs or Kafka.

## 2. The Capture (Inference -> Stream)
The system multi-casts the event:
- **Local Log**: A structured JSON entry is appended to `logs/inference.log`.
- **Kafka Stream**: A message is produced to the `inference-events` topic.
- This ensures that if the monitoring service is offline, it can "re-play" the logs later to catch up on missed drift.

## 3. The Monitoring (Stream -> Window)
The **Monitoring Service** is constantly "watching":
- A background Thread (log-tailer) picks up the new JSON entry instantly.
- The features are extracted and pushed into a **Sliding Window** (a circular buffer of size 100).
- If the buffer is full, the oldest data is evicted (FIFO - First In, First Out).

## 4. The Detection (Window -> Brain)
Every 10 new events, the **Drift Engine** awakens:
- It pulls the current 100 events from the window.
- It runs the **Kolmogorov-Smirnov (KS) Test** for each feature.
- **How it works**: It compares the distribution of the 100 live events against a "synthetic baseline" generated from the training stats. 
- If the difference (the KS-statistic) exceeds the `0.3` threshold, that feature is marked as "Drifted".

## 5. The Alerting (Brain -> Admin)
If 30% or more features are drifting:
- The system calculates **Severity**:
    - **LOW**: < 20% features drifted.
    - **MEDIUM**: < 50% features drifted.
    - **HIGH**: >= 50% features drifted.
- **Alert Banner**: A ⚠️ high-visibility message is printed to the container logs.
- **Audit Log**: A JSON entry is saved to `logs/drift_alerts.log` for future retraining triggers.

---

## 🎤 Workflow Positioning
> “The beauty of this workflow is its **Resilience**. By using a combination of persistent logs and a sliding memory window, DriftSentinel can detect both a sudden spike in bad data and a gradual shift that happens over several hours—all without ever impacting the user's prediction speed.”
