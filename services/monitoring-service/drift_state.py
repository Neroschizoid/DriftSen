"""
Drift state store — shared between the monitoring consumer thread and the API.
Keeps the latest drift result in memory so the endpoint can serve it instantly.
"""
import threading
from datetime import datetime

_lock = threading.Lock()
_latest: dict = {}


def store(result: dict) -> None:
    global _latest
    with _lock:
        _latest = {**result, "computed_at": datetime.utcnow().isoformat()}


def load() -> dict:
    with _lock:
        return dict(_latest)


def clear() -> None:
    global _latest
    with _lock:
        _latest = {}
