import os
import json
import time
from kafka import KafkaProducer
from utils.logger import logger

_producer = None

def get_producer():
    global _producer

    # 🔴 1. Disable Kafka if needed (VERY IMPORTANT)
    if os.getenv("KAFKA_ENABLED", "false").lower() != "true":
        logger.info("Kafka disabled — running in fallback mode")
        return None

    if _producer is not None:
        return _producer

    kafka_url = os.getenv("KAFKA_URL")

    if not kafka_url:
        logger.warning("KAFKA_URL not set — skipping Kafka")
        return None

    # 🔁 Retry connection
    for i in range(5):
        try:
            _producer = KafkaProducer(
                bootstrap_servers=[kafka_url],
                value_serializer=lambda v: json.dumps(v).encode("utf-8")
            )
            logger.info(f"Connected to Kafka at {kafka_url}")
            return _producer
        except Exception as e:
            logger.warning(f"Retry {i+1}/5: Kafka not ready...")
            time.sleep(2)

    logger.error("Kafka connection failed after retries")
    return None


def produce_inference_event(topic: str, request_id: str, features: dict, prediction: int, confidence: float, timestamp: str):
    producer = get_producer()

    if not producer:
        return  # ✅ SAFE EXIT

    event = {
        "timestamp": timestamp,
        "request_id": request_id,
        "features": features,
        "prediction": prediction,
        "confidence": confidence
    }

    try:
        producer.send(topic, value=event)
    except Exception as e:
        logger.error(f"Kafka send failed: {e}")