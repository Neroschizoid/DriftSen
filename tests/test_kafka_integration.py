import json
import os
import time
import uuid

import pytest
import requests
from kafka import KafkaConsumer, TopicPartition

pytestmark = pytest.mark.integration


def _wait_for_inference_health(health_url: str, timeout_sec: int = 30) -> tuple[bool, str]:
    deadline = time.time() + timeout_sec
    last_error = "unknown"
    while time.time() < deadline:
        try:
            resp = requests.get(health_url, timeout=2)
            if resp.status_code == 200:
                return True, ""
            last_error = f"status={resp.status_code}"
        except Exception as exc:
            last_error = str(exc)
        time.sleep(1)
    return False, last_error


def test_prediction_event_is_published_to_kafka():
    """
    End-to-end integration test:
    API /predict -> Kafka topic `inference-events`.
    """
    if os.getenv("RUN_KAFKA_INTEGRATION", "false").lower() != "true":
        pytest.skip("Set RUN_KAFKA_INTEGRATION=true to run Kafka integration test.")

    api_url = os.getenv("INFERENCE_API_URL", "http://localhost:8000/api/v1/predict")
    kafka_bootstrap = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:29092")
    topic = os.getenv("KAFKA_TOPIC", "inference-events")
    marker = str(uuid.uuid4())

    health_url = api_url.replace("/predict", "/health")
    healthy, reason = _wait_for_inference_health(health_url, timeout_sec=35)
    if not healthy:
        pytest.skip(f"Inference API not reachable at {api_url}: {reason}")

    payload = {
        "features": {
            "dur": 0.5,
            "spkts": 2.0,
            "dpkts": 3.0,
            "_test_marker": marker,
        }
    }
    response = requests.post(api_url, json=payload, timeout=5)
    assert response.status_code == 200, response.text

    try:
        consumer = KafkaConsumer(
            bootstrap_servers=[kafka_bootstrap],
            auto_offset_reset="earliest",
            enable_auto_commit=False,
            value_deserializer=lambda m: json.loads(m.decode("utf-8")),
            request_timeout_ms=20000,
            api_version_auto_timeout_ms=5000,
            consumer_timeout_ms=1000,
            group_id=None,
        )
    except Exception as exc:
        pytest.skip(f"Kafka not reachable at {kafka_bootstrap}: {exc}")

    try:
        partitions = None
        wait_deadline = time.time() + 10
        while time.time() < wait_deadline:
            partitions = consumer.partitions_for_topic(topic)
            if partitions:
                break
            time.sleep(0.5)

        assert partitions, f"Topic '{topic}' not available in Kafka metadata."

        consumer.assign([TopicPartition(topic, p) for p in partitions])

        deadline = time.time() + 20
        found = None
        while time.time() < deadline:
            records = consumer.poll(timeout_ms=1000)
            for messages in records.values():
                for message in messages:
                    event = message.value
                    features = event.get("features", {})
                    if isinstance(features, dict) and features.get("_test_marker") == marker:
                        found = event
                        break
                if found:
                    break
            if found:
                break

        assert found is not None, "Did not observe prediction event in Kafka topic within timeout."
        assert found["request_id"]
        assert "prediction" in found
        assert "confidence" in found
    finally:
        consumer.close()
