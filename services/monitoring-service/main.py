"""
Monitoring Service — FastAPI App
Runs the log-file / Kafka consumer in a background thread and exposes API endpoints
for drift status, dashboard visualisation, and demo orchestration.
"""
import os
import json
import time
import random
import logging
import threading
import subprocess
from collections import deque
from pathlib import Path
from contextlib import asynccontextmanager
from datetime import datetime

import requests
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from sliding_window import get_window
from drift_engine import DriftEngine
import drift_state

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("monitoring")

# -- Config ------------------------------------------------------------------
WINDOW_SIZE = int(os.getenv("WINDOW_SIZE", "100"))
DRIFT_EVERY = int(os.getenv("DRIFT_EVERY_N_EVENTS", "10"))
DRIFT_METHOD = os.getenv("DRIFT_METHOD", "ks")
KAFKA_ENABLED = os.getenv("KAFKA_ENABLED", "false").lower() == "true"
KAFKA_URL = os.getenv("KAFKA_URL", "kafka:9092")
TOPIC = "inference-events"
INFERENCE_URL = os.getenv("INFERENCE_URL", "http://inference:8000/api/v1")

SERVICE_DIR = Path(__file__).resolve().parent
ROOT_DIR = SERVICE_DIR.parents[1]
LOG_FILE = str((ROOT_DIR / "logs" / "inference.log").resolve())
ALERT_LOG = str((ROOT_DIR / "logs" / "drift_alerts.log").resolve())
BASELINE_PATH = str((ROOT_DIR / "ml" / "stats" / "baseline_stats.json").resolve())

REQUIRED = {"timestamp", "request_id", "features", "prediction", "confidence"}
DASHBOARD_DIR = SERVICE_DIR / "dashboard"
DASHBOARD_STATIC_DIR = DASHBOARD_DIR / "static"

DEMO_LOCK = threading.Lock()
DEMO_STOP = threading.Event()
DEMO_THREAD: threading.Thread | None = None
DEMO_LOGS: deque[str] = deque(maxlen=1200)
DEMO_STATE = {
    "running": False,
    "mode": "idle",
    "progress": 0,
    "iterations": 0,
    "command_running": False,
    "active_command": "",
    "updated_at": "",
}
BASELINE_CACHE: dict | None = None


class DemoRunRequest(BaseModel):
    mode: str = Field(default="gradual")
    iterations: int = Field(default=60, ge=1, le=2000)
    interval_ms: int = Field(default=300, ge=50, le=10000)


class DemoCommandRequest(BaseModel):
    command: str


def _now() -> str:
    return datetime.utcnow().isoformat()


def _demo_log(line: str) -> None:
    stamp = datetime.now().strftime("%I:%M:%S %p")
    msg = f"[{stamp}] {line}"
    DEMO_LOGS.append(msg)
    logger.info(f"[DEMO] {line}")
    DEMO_STATE["updated_at"] = _now()


def _tail_file(path: str, lines: int = 20) -> list[str]:
    p = Path(path)
    if not p.exists():
        return [f"File not found: {path}"]
    with p.open("r", encoding="utf-8", errors="ignore") as f:
        data = f.readlines()
    return [line.rstrip("\n") for line in data[-lines:]]


def _valid(event: dict) -> bool:
    return not (REQUIRED - event.keys())


def _alert(result: dict) -> None:
    severity = result.get("drift_severity", "UNKNOWN")
    msg = (
        f"\n⚠ DRIFT DETECTED\n"
        f"Severity         : {severity}\n"
        f"Drift Score      : {result['drift_score']}\n"
        f"Affected Features: {result['features_drifted']}/{result['features_checked']}\n"
    )
    logger.warning(msg)
    os.makedirs(os.path.dirname(ALERT_LOG), exist_ok=True)
    with open(ALERT_LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps({
            "alert": "drift_detected",
            "severity": severity,
            "drift_score": result["drift_score"],
            "features_drifted": result["features_drifted"],
            "features_checked": result["features_checked"],
            "computed_at": result.get("computed_at", ""),
        }) + "\n")


# -- Consumer logic ----------------------------------------------------------
def _consumer_loop() -> None:
    window = get_window(WINDOW_SIZE)
    engine = DriftEngine(method=DRIFT_METHOD)
    count = 0

    def process(event: dict) -> None:
        nonlocal count
        if not _valid(event):
            return
        window.add(event)
        count += 1
        logger.info(
            f"✅ #{count} | pred={event.get('prediction')} "
            f"conf={float(event.get('confidence', 0)):.3f} | "
            f"window={window.size}/{window.maxsize}"
        )
        if count % DRIFT_EVERY == 0:
            result = engine.compare(window)
            drift_state.store(result)
            logger.info(
                f"📊 Drift | score={result['drift_score']} "
                f"detected={result['drift_detected']} "
                f"({result['features_drifted']}/{result['features_checked']} features)"
            )
            if result["drift_detected"]:
                _alert(result)

    if KAFKA_ENABLED:
        _kafka_loop(process)
    else:
        _log_tail(process)


def _kafka_loop(fn):
    from kafka import KafkaConsumer

    logger.info(f"🔗 Kafka -> {KAFKA_URL}/{TOPIC}")
    kafka_kwargs = {}
    security_protocol = os.getenv("KAFKA_SECURITY_PROTOCOL", "PLAINTEXT").strip().upper()
    if security_protocol:
        kafka_kwargs["security_protocol"] = security_protocol

    username = os.getenv("KAFKA_USERNAME", "").strip()
    password = os.getenv("KAFKA_PASSWORD", "").strip()
    mechanism = os.getenv("KAFKA_SASL_MECHANISM", "PLAIN").strip().upper()
    if username and password:
        kafka_kwargs["sasl_mechanism"] = mechanism
        kafka_kwargs["sasl_plain_username"] = username
        kafka_kwargs["sasl_plain_password"] = password

    cafile = os.getenv("KAFKA_SSL_CAFILE", "").strip()
    certfile = os.getenv("KAFKA_SSL_CERTFILE", "").strip()
    keyfile = os.getenv("KAFKA_SSL_KEYFILE", "").strip()
    if cafile:
        kafka_kwargs["ssl_cafile"] = cafile
    if certfile:
        kafka_kwargs["ssl_certfile"] = certfile
    if keyfile:
        kafka_kwargs["ssl_keyfile"] = keyfile

    consumer = KafkaConsumer(
        TOPIC,
        bootstrap_servers=[KAFKA_URL],
        auto_offset_reset="earliest",
        value_deserializer=lambda m: json.loads(m.decode("utf-8")),
        group_id="monitoring-service",
        **kafka_kwargs,
    )
    for msg in consumer:
        fn(msg.value)


def _log_tail(fn):
    logger.info(f"📄 Tailing {LOG_FILE}")
    while not os.path.exists(LOG_FILE):
        logger.warning("Log file not found — retrying in 2s...")
        time.sleep(2)
    with open(LOG_FILE, "r", encoding="utf-8", errors="ignore") as f:
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
                fn(json.loads(line))
            except json.JSONDecodeError:
                pass


# -- Demo orchestration ------------------------------------------------------
def _load_baseline() -> dict:
    global BASELINE_CACHE
    if BASELINE_CACHE is None:
        with open(BASELINE_PATH, "r", encoding="utf-8") as f:
            BASELINE_CACHE = json.load(f)
    return BASELINE_CACHE


def _make_features(mode: str, step: int, total: int) -> dict:
    baseline = _load_baseline()
    vec = {}

    if mode == "normal":
        factor = 1.0
        sigma_scale = 1.0
    elif mode == "gradual":
        progress = step / max(total, 1)
        factor = 1.0 + (0.85 * progress)
        sigma_scale = 1.0 + (0.35 * progress)
    else:  # sudden
        factor = 11.0
        sigma_scale = 2.4

    for name, stats in baseline.items():
        mean = float(stats.get("mean", 0.0))
        std = float(stats.get("std", 1.0)) or 1.0
        value = random.gauss(mean * factor, std * sigma_scale)
        vec[name] = float(value)
    return vec


def _get_drift_snapshot() -> dict:
    current = drift_state.load()
    if current:
        return current
    return {
        "drift_score": 0.0,
        "drift_detected": False,
        "drift_severity": "NONE",
        "features_checked": 0,
        "features_drifted": 0,
    }


def _send_inference(features: dict) -> float:
    started = time.perf_counter()
    response = requests.post(f"{INFERENCE_URL}/predict", json={"features": features}, timeout=8)
    response.raise_for_status()
    return (time.perf_counter() - started) * 1000.0


def _icon(detected: bool) -> str:
    return "🔴" if detected else "🟢"


def _run_mode(mode: str, iterations: int, interval_ms: int) -> None:
    with DEMO_LOCK:
        DEMO_STATE["running"] = True
        DEMO_STATE["mode"] = mode
        DEMO_STATE["progress"] = 0
        DEMO_STATE["iterations"] = iterations

    _demo_log(f"🚀 MODE: {mode.upper()} | Iterations: {iterations}")
    _demo_log("------------------------------------------------------------")

    for i in range(1, iterations + 1):
        if DEMO_STOP.is_set():
            _demo_log("⏹ Demo stopped by user.")
            break

        features = _make_features(mode, i, iterations)
        try:
            latency_ms = _send_inference(features)
        except Exception as exc:
            _demo_log(f"[{i:02d}/{iterations}] ❌ Inference error: {exc}")
            break

        snapshot = _get_drift_snapshot()
        score = float(snapshot.get("drift_score", 0.0))
        detected = bool(snapshot.get("drift_detected", False))
        severity = snapshot.get("drift_severity", "NONE") if detected else "NONE"

        _demo_log(
            f"[{i:02d}/{iterations}] {_icon(detected)} "
            f"Latency: {latency_ms:4.1f}ms | Drift Score: {score:.4f} | Severity: {severity}"
        )

        DEMO_STATE["progress"] = i
        time.sleep(max(interval_ms, 50) / 1000.0)

    _demo_log("------------------------------------------------------------")
    _demo_log("✅ Demo sequence complete.")
    DEMO_STATE["running"] = False
    DEMO_STATE["mode"] = "idle"


def _run_command(command: str) -> None:
    DEMO_STATE["command_running"] = True
    DEMO_STATE["active_command"] = command
    _demo_log(f"$ {command}")

    try:
        if command == "verify_health":
            inf = requests.get(f"{INFERENCE_URL}/health", timeout=5)
            mon = requests.get("http://localhost:8001/api/v1/monitoring/health", timeout=5)
            _demo_log(f"inference health -> {inf.status_code} {inf.text}")
            _demo_log(f"monitoring health -> {mon.status_code} {mon.text}")

        elif command == "inference_sample":
            resp = requests.post(f"{INFERENCE_URL}/predict", json={"features": [0.1, 0.2, 0.3, 0.4, 0.5]}, timeout=8)
            _demo_log(f"predict -> {resp.status_code} {resp.text}")

        elif command == "show_drift":
            snapshot = requests.get("http://localhost:8001/api/v1/monitoring/drift", timeout=5)
            _demo_log(f"drift -> {snapshot.status_code} {snapshot.text}")

        elif command == "show_audit_logs":
            _demo_log("tail -n 20 logs/inference.log")
            for line in _tail_file(LOG_FILE, 20):
                _demo_log(line)
            _demo_log("tail -n 20 logs/drift_alerts.log")
            for line in _tail_file(ALERT_LOG, 20):
                _demo_log(line)

        elif command in {"unit_tests", "kafka_integration_test"}:
            env = os.environ.copy()
            if command == "unit_tests":
                cmd = ["python3", "-m", "pytest", "-q"]
            else:
                cmd = ["python3", "-m", "pytest", "-q", "tests/test_kafka_integration.py", "-m", "integration"]
                env["RUN_KAFKA_INTEGRATION"] = "true"
                env["KAFKA_BOOTSTRAP_SERVERS"] = env.get("KAFKA_BOOTSTRAP_SERVERS", "kafka:9092")

            proc = subprocess.Popen(
                cmd,
                cwd=str(ROOT_DIR),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                env=env,
            )
            assert proc.stdout is not None
            for line in proc.stdout:
                _demo_log(line.rstrip("\n"))
            code = proc.wait()
            _demo_log(f"command exit code: {code}")

        elif command == "shutdown_stack":
            cmd = ["docker", "compose", "down"]
            proc = subprocess.Popen(
                cmd,
                cwd=str(ROOT_DIR),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
            )
            assert proc.stdout is not None
            for line in proc.stdout:
                _demo_log(line.rstrip("\n"))
            code = proc.wait()
            _demo_log(f"command exit code: {code}")

        else:
            _demo_log(f"Unknown command: {command}")

    except Exception as exc:
        _demo_log(f"❌ Command failed: {exc}")
    finally:
        DEMO_STATE["command_running"] = False
        DEMO_STATE["active_command"] = ""


# -- Lifespan ----------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    t = threading.Thread(target=_consumer_loop, daemon=True)
    t.start()
    logger.info("🛡 Monitoring consumer started")
    yield


# -- FastAPI app -------------------------------------------------------------
app = FastAPI(
    title="DriftSentinel — Monitoring Service",
    description="Real-time drift detection for the inference pipeline.",
    version="3.0.0",
    lifespan=lifespan,
)

if DASHBOARD_STATIC_DIR.exists():
    app.mount("/dashboard/static", StaticFiles(directory=str(DASHBOARD_STATIC_DIR)), name="dashboard-static")


@app.get("/dashboard", include_in_schema=False)
def dashboard():
    index_path = DASHBOARD_DIR / "index.html"
    if not index_path.exists():
        return JSONResponse(
            status_code=404,
            content={"error": "Dashboard is not available. Expected services/monitoring-service/dashboard/index.html"},
        )
    return FileResponse(index_path)


@app.get("/api/v1/monitoring/health")
def health():
    return {"status": "healthy", "timestamp": datetime.utcnow().isoformat()}


@app.get("/api/v1/monitoring/config")
def monitoring_config():
    return {
        "window_size": WINDOW_SIZE,
        "drift_every_n_events": DRIFT_EVERY,
        "drift_method": DRIFT_METHOD,
        "kafka_enabled": KAFKA_ENABLED,
        "kafka_url": KAFKA_URL,
        "topic": TOPIC,
        "inference_url": INFERENCE_URL,
    }


@app.post("/api/v1/monitoring/reset_state")
def reset_state():
    get_window(WINDOW_SIZE).clear()
    drift_state.clear()
    DEMO_LOGS.clear()
    _demo_log("State reset: window cleared, drift state cleared.")
    return {"ok": True}


@app.get("/api/v1/monitoring/window")
def window_info():
    return get_window(WINDOW_SIZE).summary()


@app.get("/api/v1/monitoring/drift")
def drift_status():
    result = drift_state.load()
    if not result:
        return JSONResponse(
            status_code=200,
            content={
                "drift_score": 0.0,
                "drift_detected": False,
                "drift_severity": "NONE",
                "features_checked": 0,
                "features_drifted": 0,
                "window_size": get_window(WINDOW_SIZE).size,
                "note": (
                    f"No drift computed yet. Window needs {DRIFT_EVERY} events — "
                    f"currently at {get_window(WINDOW_SIZE).size}."
                ),
            },
        )
    return result


@app.get("/api/v1/monitoring/logs/{log_name}")
def fetch_logs(log_name: str, lines: int = 20):
    if lines < 1 or lines > 500:
        raise HTTPException(status_code=400, detail="lines must be between 1 and 500")
    if log_name == "inference":
        return {"log": "inference", "lines": _tail_file(LOG_FILE, lines)}
    if log_name == "alerts":
        return {"log": "alerts", "lines": _tail_file(ALERT_LOG, lines)}
    raise HTTPException(status_code=404, detail="log_name must be 'inference' or 'alerts'")


@app.get("/api/v1/monitoring/demo/status")
def demo_status(lines: int = 120):
    if lines < 1 or lines > 1200:
        raise HTTPException(status_code=400, detail="lines must be between 1 and 1200")
    return {
        **DEMO_STATE,
        "logs": list(DEMO_LOGS)[-lines:],
    }


@app.post("/api/v1/monitoring/demo/run")
def demo_run(req: DemoRunRequest):
    mode = req.mode.lower().strip()
    if mode not in {"normal", "gradual", "sudden"}:
        raise HTTPException(status_code=400, detail="mode must be one of: normal, gradual, sudden")

    global DEMO_THREAD
    if DEMO_STATE["running"]:
        raise HTTPException(status_code=409, detail="A demo run is already in progress")

    DEMO_STOP.clear()
    DEMO_THREAD = threading.Thread(
        target=_run_mode,
        args=(mode, req.iterations, req.interval_ms),
        daemon=True,
    )
    DEMO_THREAD.start()
    return {"ok": True, "mode": mode, "iterations": req.iterations, "interval_ms": req.interval_ms}


@app.post("/api/v1/monitoring/demo/stop")
def demo_stop():
    DEMO_STOP.set()
    return {"ok": True}


@app.post("/api/v1/monitoring/demo/command")
def demo_command(req: DemoCommandRequest):
    command = req.command.strip()
    if DEMO_STATE["command_running"]:
        raise HTTPException(status_code=409, detail="Another command is already running")

    allowed = {
        "verify_health",
        "inference_sample",
        "show_drift",
        "show_audit_logs",
        "unit_tests",
        "kafka_integration_test",
        "shutdown_stack",
    }
    if command not in allowed:
        raise HTTPException(status_code=400, detail=f"Unsupported command. Allowed: {sorted(allowed)}")

    t = threading.Thread(target=_run_command, args=(command,), daemon=True)
    t.start()
    return {"ok": True, "command": command}


if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("MONITORING_PORT", 8001))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=False)
