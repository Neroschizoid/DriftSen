import os
import json
from kafka import KafkaProducer
from utils.logger import logger

_producer = None

import time

def get_producer():
    global _producer
    if _producer is None:
        if os.getenv("KAFKA_ENABLED", "true").lower() == "false":
            logger.info("Kafka is disabled via environment variable.")
            return None

        kafka_url = os.getenv("KAFKA_URL", "kafka:9092")
        for i in range(10):  # retry
            try:
                _producer = KafkaProducer(
                    bootstrap_servers=[kafka_url],
                    value_serializer=lambda v: json.dumps(v).encode("utf-8"),
                    api_version=(2, 8, 1)
                )
                logger.info(f"Kafka connected to {kafka_url}")
                return _producer
            except Exception as e:
                logger.warning(f"Retry {i+1}/10: Kafka not ready...")
                time.sleep(2)

        logger.error("Kafka connection failed after retries")
        return None

    return _producer

def produce_inference_event(topic: str, request_id: str, features: dict, prediction: int, confidence: float, timestamp: str):
    producer = get_producer()
    if producer:
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
            logger.error(f"Failed to produce Kafka message: {e}")
