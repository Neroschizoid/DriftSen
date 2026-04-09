"""
Monitoring Service — Week 2 Phase 1 + Phase 2
Consumes events from the 'inference-events' Kafka topic (or reads from the JSON log file as fallback),
validates event fields, feeds each event into a sliding window buffer, and prints a live data stream.
"""
import os
import json
import time
import logging
from datetime import datetime

from sliding_window import get_window

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("monitoring")

WINDOW_SIZE = int(os.getenv("WINDOW_SIZE", "100"))

KAFKA_ENABLED = os.getenv("KAFKA_ENABLED", "false").lower() == "true"
KAFKA_URL     = os.getenv("KAFKA_URL", "kafka:9092")
TOPIC         = "inference-events"
LOG_FILE      = os.path.join(os.path.dirname(__file__), "../../logs/inference.log")

REQUIRED_FIELDS = {"timestamp", "request_id", "features", "prediction", "confidence"}


def validate_event(event: dict) -> bool:
    missing = REQUIRED_FIELDS - event.keys()
    if missing:
        logger.warning(f"⚠️  Missing fields in event: {missing}")
        return False
    if not isinstance(event.get("features"), (dict, list)):
        logger.warning("⚠️  'features' field is not a dict or list")
        return False
    if event.get("prediction") is None:
        logger.warning("⚠️  'prediction' field is None")
        return False
    return True


# ─────────────────────────────────────────────────────────────
# MODE A: Kafka Consumer
# ─────────────────────────────────────────────────────────────
def consume_kafka():
    from kafka import KafkaConsumer
    logger.info(f"🔗 Connecting to Kafka at {KAFKA_URL} → topic '{TOPIC}'")
    consumer = KafkaConsumer(
        TOPIC,
        bootstrap_servers=[KAFKA_URL],
        auto_offset_reset="earliest",
        value_deserializer=lambda m: json.loads(m.decode("utf-8")),
        group_id="monitoring-service",
    )
    logger.info("✅ Kafka Consumer connected — listening for events...\n")
    window = get_window(WINDOW_SIZE)
    for message in consumer:
        event = message.value
        ts    = event.get("timestamp", "N/A")
        rid   = event.get("request_id", "N/A")[:8]
        pred  = event.get("prediction", "N/A")
        conf  = float(event.get("confidence", 0))
        valid = validate_event(event)
        if valid:
            window.add(event)
        status = "✅" if valid else "❌"
        logger.info(f"{status}  [{ts}] req={rid}… pred={pred} conf={conf:.3f}  |  "
                    f"Current window size: {window.size}/{window.maxsize}")


# ─────────────────────────────────────────────────────────────
# MODE B: Log‑file Tail (fallback — works without Kafka)
# ─────────────────────────────────────────────────────────────
def tail_log_file():
    logger.info(f"📄 Kafka disabled — tailing log file: {LOG_FILE}")
    if not os.path.exists(LOG_FILE):
        logger.error(f"Log file not found: {LOG_FILE}")
        return

    logger.info("✅ Log file found — watching for new events...\n")
    window = get_window(WINDOW_SIZE)
    event_count = 0
    with open(LOG_FILE, "r") as f:
        # Skip to end of existing content (only tail NEW lines)
        f.seek(0, 2)
        while True:
            line = f.readline()
            if not line:
                time.sleep(0.5)
                continue
            line = line.strip()
            if not line:
                continue
            try:
                event = json.loads(line)
                ts    = event.get("timestamp", "N/A")
                rid   = event.get("request_id", "N/A")[:8]
                pred  = event.get("prediction", "N/A")
                conf  = float(event.get("confidence", 0))
                valid = validate_event(event)
                if valid:
                    window.add(event)
                    event_count += 1
                status = "✅" if valid else "❌"
                logger.info(f"{status}  [{ts}] req={rid}… pred={pred} conf={conf:.3f}  |  "
                            f"Current window size: {window.size}/{window.maxsize}")
                # Print full summary every 10 events
                if event_count > 0 and event_count % 10 == 0:
                    logger.info(f"📊 Window summary: {window.summary()}")
            except json.JSONDecodeError:
                logger.warning(f"Could not parse line: {line[:60]}")


# ─────────────────────────────────────────────────────────────
# Entry Point
# ─────────────────────────────────────────────────────────────
if __name__ == "__main__":
    logger.info("🛡  DriftSentinel — Monitoring Service (Phase 1 + Phase 2)")
    logger.info(f"   Mode: {'Kafka Consumer' if KAFKA_ENABLED else 'Log-file Tail'}")
    logger.info(f"   Window Size: {WINDOW_SIZE}\n")
    try:
        if KAFKA_ENABLED:
            consume_kafka()
        else:
            tail_log_file()
    except KeyboardInterrupt:
        logger.info("Monitoring stopped.")
