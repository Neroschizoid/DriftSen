"""
Sliding Window Buffer — Week 2 Phase 2
Thread-safe, fixed-size circular buffer for recent inference events.
Automatically evicts old entries when full (no memory overflow).
"""
from collections import deque
from threading import Lock
from datetime import datetime


class SlidingWindow:
    """
    Fixed-size FIFO buffer for inference events.
    When full, the oldest entry is automatically removed (deque maxlen).
    Thread-safe via a Lock — safe for concurrent producer/consumer access.
    """

    def __init__(self, maxsize: int = 100):
        self._maxsize = maxsize
        self._buffer: deque = deque(maxlen=maxsize)   # auto-evicts oldest on overflow
        self._lock = Lock()

    # ── Write ────────────────────────────────────────────────
    def add(self, event: dict) -> None:
        """Add a new event to the window. Evicts oldest if full."""
        entry = {
            "timestamp": event.get("timestamp", datetime.utcnow().isoformat()),
            "request_id": event.get("request_id"),
            "features": event.get("features"),
            "prediction": event.get("prediction"),
            "confidence": event.get("confidence"),
        }
        with self._lock:
            self._buffer.append(entry)

    # ── Read ─────────────────────────────────────────────────
    def get_all(self) -> list:
        """Return a snapshot of current window contents (thread-safe copy)."""
        with self._lock:
            return list(self._buffer)

    def get_features(self) -> list:
        """Return only the feature vectors from the current window."""
        with self._lock:
            return [e["features"] for e in self._buffer if e["features"] is not None]

    def get_timestamps(self) -> list:
        """Return only the timestamps from the current window."""
        with self._lock:
            return [e["timestamp"] for e in self._buffer]

    def clear(self) -> None:
        """Clear all buffered events."""
        with self._lock:
            self._buffer.clear()

    # ── Introspection ────────────────────────────────────────
    @property
    def size(self) -> int:
        with self._lock:
            return len(self._buffer)

    @property
    def maxsize(self) -> int:
        return self._maxsize

    @property
    def is_full(self) -> bool:
        return self.size >= self._maxsize

    def summary(self) -> dict:
        with self._lock:
            return {
                "current_window_size": len(self._buffer),
                "max_window_size": self._maxsize,
                "is_full": len(self._buffer) >= self._maxsize,
                "oldest_timestamp": self._buffer[0]["timestamp"] if self._buffer else None,
                "newest_timestamp": self._buffer[-1]["timestamp"] if self._buffer else None,
            }

    def __repr__(self) -> str:
        return f"SlidingWindow(size={self.size}/{self._maxsize})"


# ── Singleton shared across the monitoring service ───────────
_window: SlidingWindow | None = None


def get_window(maxsize: int = 100) -> SlidingWindow:
    """Return (or create) the global sliding window singleton."""
    global _window
    if _window is None:
        _window = SlidingWindow(maxsize=maxsize)
    return _window


def reset_window(maxsize: int = 100) -> SlidingWindow:
    """Replace and return the shared window instance."""
    global _window
    _window = SlidingWindow(maxsize=maxsize)
    return _window
