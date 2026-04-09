import os
import time

import pytest
import requests

pytestmark = pytest.mark.integration

BASE_URL = os.getenv("INFERENCE_API_BASE", "http://localhost:8000/api/v1")
PREDICT_URL = f"{BASE_URL}/predict"
HEALTH_URL = f"{BASE_URL}/health"


def _wait_for_health(timeout_sec: int = 40) -> tuple[bool, str]:
    deadline = time.time() + timeout_sec
    last_error = "unknown"
    while time.time() < deadline:
        try:
            response = requests.get(HEALTH_URL, timeout=2)
            if response.status_code == 200:
                return True, ""
            last_error = f"status={response.status_code}"
        except Exception as exc:
            last_error = str(exc)
        time.sleep(1)
    return False, last_error


@pytest.fixture(scope="module", autouse=True)
def require_running_api():
    if os.getenv("RUN_API_INTEGRATION", "false").lower() != "true":
        pytest.skip("Set RUN_API_INTEGRATION=true to run API integration tests.")
    ok, reason = _wait_for_health()
    if not ok:
        pytest.skip(f"Inference API not reachable at {HEALTH_URL}: {reason}")


@pytest.mark.parametrize(
    "features",
    [
        [0.1, 0.2, 0.3, 0.4, 0.5],
        [1, 1, 1, 1, 1],
        [0, 0, 0, 0, 0],
        [5, 2, 3, 1, 0],
    ],
)
def test_predict_with_list_features(features):
    response = requests.post(PREDICT_URL, json={"features": features}, timeout=5)
    assert response.status_code == 200, response.text
    body = response.json()
    assert "request_id" in body
    assert "prediction" in body
    assert "confidence" in body
    assert body["prediction"] in (0, 1)
    assert 0.0 <= float(body["confidence"]) <= 1.0


def test_predict_rejects_invalid_feature_payload():
    response = requests.post(PREDICT_URL, json={"features": ["a", "b"]}, timeout=5)
    assert response.status_code == 422


def test_predict_throughput_20_requests_under_8_seconds():
    start = time.time()
    for _ in range(20):
        response = requests.post(PREDICT_URL, json={"features": [0.1, 0.2, 0.3, 0.4, 0.5]}, timeout=5)
        assert response.status_code == 200
    duration = time.time() - start
    assert duration < 8.0, f"20 requests took {duration:.3f}s"
