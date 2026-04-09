"""
Drift Simulator — Week 2 Phase 5
Sends two rounds of data to the monitoring log:
  Round 1: Normal data  → drift_detected = False
  Round 2: Drifted data → drift_detected = True

Run this while the monitoring service (main.py) is already running on port 8001.
"""
import json
import uuid
import random
import time
import urllib.request
from datetime import datetime

LOG_FILE     = "logs/inference.log"
MONITOR_URL  = "http://localhost:8001/api/v1/monitoring/drift"
BASELINE_PATH = "ml/stats/baseline_stats.json"


def load_baseline():
    with open(BASELINE_PATH) as f:
        return json.load(f)


def write_events(baseline: dict, n: int, multiplier: float, label: str):
    """Write n events to the log. multiplier shifts features away from baseline."""
    keys = list(baseline.keys())
    print(f"\n[{label}] Writing {n} events (feature multiplier x{multiplier})...")
    with open(LOG_FILE, "a") as f:
        for i in range(n):
            vec = {
                k: (baseline[k]["mean"] + baseline[k]["std"] * random.gauss(0, 1.0))
                   * multiplier
                for k in keys
            }
            f.write(json.dumps({
                "timestamp":  datetime.utcnow().isoformat(),
                "request_id": str(uuid.uuid4()),
                "features":   vec,
                "prediction": random.randint(0, 1),
                "confidence": round(random.uniform(0.6, 0.99), 3),
            }) + "\n")
            time.sleep(0.1)
    print(f"[{label}] {n} events written.")


def get_drift_status():
    try:
        resp = urllib.request.urlopen(MONITOR_URL, timeout=3)
        return json.loads(resp.read())
    except Exception as e:
        return {"error": str(e)}


def print_result(label: str, result: dict):
    detected = result.get("drift_detected", "N/A")
    score    = result.get("drift_score", "N/A")
    checked  = result.get("features_checked", 0)
    drifted  = result.get("features_drifted", 0)
    icon     = "🔴 DRIFT DETECTED" if detected else "🟢 No drift"
    print(f"\n{'='*55}")
    print(f"  {label}")
    print(f"  {icon}")
    print(f"  drift_score     : {score}")
    print(f"  features_drifted: {drifted}/{checked}")
    print(f"{'='*55}")


if __name__ == "__main__":
    print("🛡  DriftSentinel — Drift Simulation Demo")
    print(f"   Monitoring API : {MONITOR_URL}")
    print(f"   Log file       : {LOG_FILE}\n")

    baseline = load_baseline()

    # ── Round 1: Normal data ──────────────────────────────────
    write_events(baseline, n=30, multiplier=1.0, label="NORMAL")
    time.sleep(3)
    r1 = get_drift_status()
    print_result("Round 1 — NORMAL data (multiplier x1.0)", r1)

    # ── Round 2: Drifted data (features × 15) ────────────────
    write_events(baseline, n=60, multiplier=15.0, label="DRIFTED")
    time.sleep(3)
    r2 = get_drift_status()
    print_result("Round 2 — DRIFTED data (multiplier x15.0)", r2)

    # ── Summary ───────────────────────────────────────────────
    print("\n📊 SIMULATION SUMMARY")
    print(f"   Normal  → drift_detected: {r1.get('drift_detected')}")
    print(f"   Drifted → drift_detected: {r2.get('drift_detected')}")
    ok = r1.get("drift_detected") is False and r2.get("drift_detected") is True
    print(f"\n{'✅ DEMO PASSED' if ok else '❌ DEMO FAILED — check window/threshold config'}")
