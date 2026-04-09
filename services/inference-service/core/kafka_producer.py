import os
import json
import time
from kafka import KafkaProducer
from utils.logger import logger

_producer = None


def _kafka_client_kwargs() -> dict:
    kwargs = {}
    security_protocol = os.getenv("KAFKA_SECURITY_PROTOCOL", "PLAINTEXT").strip().upper()
    if security_protocol:
        kwargs["security_protocol"] = security_protocol

    # SASL is optional and only applied when credentials are provided.
    username = os.getenv("KAFKA_USERNAME", "").strip()
    password = os.getenv("KAFKA_PASSWORD", "").strip()
    mechanism = os.getenv("KAFKA_SASL_MECHANISM", "PLAIN").strip().upper()
    if username and password:
        kwargs["sasl_mechanism"] = mechanism
        kwargs["sasl_plain_username"] = username
        kwargs["sasl_plain_password"] = password

    # TLS files are optional for managed Kafka providers that require custom certs.
    cafile = os.getenv("KAFKA_SSL_CAFILE", "").strip()
    certfile = os.getenv("KAFKA_SSL_CERTFILE", "").strip()
    keyfile = os.getenv("KAFKA_SSL_KEYFILE", "").strip()
    if cafile:
        kwargs["ssl_cafile"] = cafile
    if certfile:
        kwargs["ssl_certfile"] = certfile
    if keyfile:
        kwargs["ssl_keyfile"] = keyfile

    return kwargs

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
                value_serializer=lambda v: json.dumps(v).encode("utf-8"),
                **_kafka_client_kwargs(),
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
        # Wait for broker ack so tests and monitoring can reliably observe the event.
        producer.send(topic, value=event).get(timeout=5)
    except Exception as e:
        logger.error(f"Kafka send failed: {e}")
