from pathlib import Path
import sys

MONITORING_DIR = Path(__file__).resolve().parents[1] / "services" / "monitoring-service"
sys.path.insert(0, str(MONITORING_DIR))

from drift_engine import DriftEngine  # noqa: E402
from sliding_window import SlidingWindow  # noqa: E402


def test_sliding_window_eviction():
    window = SlidingWindow(maxsize=3)
    for i in range(5):
        window.add(
            {
                "timestamp": f"t{i}",
                "request_id": f"r{i}",
                "features": {"dur": float(i)},
                "prediction": 0,
                "confidence": 0.5,
            }
        )
    items = window.get_all()
    assert window.size == 3
    assert items[0]["request_id"] == "r2"
    assert items[-1]["request_id"] == "r4"


def test_drift_engine_compare_on_empty_window():
    window = SlidingWindow(maxsize=5)
    engine = DriftEngine(method="zscore")
    result = engine.compare(window)
    assert result["drift_detected"] is False
    assert result["features_checked"] == 0


def test_drift_engine_generates_feature_report():
    window = SlidingWindow(maxsize=10)
    for i in range(10):
        window.add(
            {
                "timestamp": f"t{i}",
                "request_id": f"r{i}",
                "features": {"dur": float(i + 1), "spkts": float(i + 2)},
                "prediction": i % 2,
                "confidence": 0.8,
            }
        )
    engine = DriftEngine(method="zscore")
    result = engine.compare(window)
    assert result["features_checked"] >= 1
    assert isinstance(result["feature_report"], list)
