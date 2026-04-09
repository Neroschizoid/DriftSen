"""
DriftEngine — Week 2 Phase 3
Compares baseline statistics (from Week 1) against the current sliding window.

Two detection methods:
  - Option A: Mean Z-score difference (fast, interpretable)
  - Option B: KS test (statistical, more robust)

Outputs a per-feature drift report and an overall drift_detected boolean.
"""
import json
import os
import math
import logging
from typing import Any

logger = logging.getLogger("monitoring.drift")

BASELINE_PATH = os.path.join(
    os.path.dirname(__file__), "../../ml/stats/baseline_stats.json"
)

# Drift is flagged if the mean deviation exceeds this many standard deviations
ZSCORE_THRESHOLD = float(os.getenv("DRIFT_ZSCORE_THRESHOLD", "3.0"))
# KS statistic threshold (0–1); higher = more drift required to trigger
KS_THRESHOLD     = float(os.getenv("DRIFT_KS_THRESHOLD",     "0.3"))
# Fraction of features that must drift before overall flag is raised
FEATURE_RATIO    = float(os.getenv("DRIFT_FEATURE_RATIO",    "0.3"))


def get_severity(score: float) -> str:
    """Classifies drift impact into enterprise-ready tiers."""
    if score < 0.2:
        return "LOW"
    elif score < 0.5:
        return "MEDIUM"
    else:
        return "HIGH"


def _load_baseline() -> dict:
    with open(BASELINE_PATH, "r") as f:
        return json.load(f)


def _safe_mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def _safe_std(values: list[float]) -> float:
    if len(values) < 2:
        return 0.0
    m = _safe_mean(values)
    variance = sum((v - m) ** 2 for v in values) / (len(values) - 1)
    return math.sqrt(variance)


# ─────────────────────────────────────────────────────────────
# Option A – Z-score mean difference
# ─────────────────────────────────────────────────────────────
def _zscore_drift(feature: str, baseline: dict, live_values: list[float]) -> dict:
    stats   = baseline.get(feature, {})
    b_mean  = stats.get("mean", 0.0)
    b_std   = stats.get("std",  1.0) or 1.0       # avoid div-by-zero
    l_mean  = _safe_mean(live_values)
    z_score = abs(l_mean - b_mean) / b_std
    return {
        "feature":        feature,
        "method":         "zscore",
        "baseline_mean":  round(b_mean, 4),
        "live_mean":      round(l_mean, 4),
        "z_score":        round(z_score, 4),
        "drift_detected": z_score > ZSCORE_THRESHOLD,
    }


# ─────────────────────────────────────────────────────────────
# Option B – Kolmogorov-Smirnov test (requires scipy)
# ─────────────────────────────────────────────────────────────
def _ks_drift(feature: str, baseline: dict, live_values: list[float]) -> dict:
    try:
        from scipy import stats as sp_stats
        import numpy as np

        b_stats  = baseline.get(feature, {})
        b_mean   = b_stats.get("mean", 0.0)
        b_std    = b_stats.get("std",  1.0) or 1.0
        # Synthesise a reference sample from baseline distribution
        rng      = np.random.default_rng(42)
        baseline_sample = rng.normal(b_mean, b_std, max(len(live_values) * 2, 200))
        ks_stat, p_val  = sp_stats.ks_2samp(baseline_sample, live_values)
        return {
            "feature":        feature,
            "method":         "ks_test",
            "ks_statistic":   round(float(ks_stat), 4),
            "p_value":        round(float(p_val), 4),
            "drift_detected": bool(ks_stat > KS_THRESHOLD),
        }
    except ImportError:
        # scipy not available — fall back to z-score
        logger.warning("scipy not installed, falling back to z-score for KS test")
        return _zscore_drift(feature, baseline, live_values)


class DriftEngine:
    """
    Compares baseline stats against data in a SlidingWindow.
    Usage:
        engine = DriftEngine()
        result = engine.compare(window)
    """

    def __init__(self, method: str = "zscore"):
        """
        method: "zscore" (Option A) or "ks" (Option B)
        """
        self.method   = method
        self.baseline = _load_baseline()
        logger.info(
            f"DriftEngine initialised | method={method} | "
            f"{len(self.baseline)} baseline features loaded"
        )

    def compare(self, window) -> dict:
        """
        Run drift detection against the current sliding window.

        Returns:
        {
            "window_size": int,
            "features_checked": int,
            "features_drifted": int,
            "drift_score": float,          # fraction of features drifted
            "drift_detected": bool,
            "feature_report": [ {...}, ... ]
        }
        """
        raw_features = window.get_features()   # list of feature vectors

        if not raw_features:
            return {
                "window_size":       window.size,
                "features_checked":  0,
                "features_drifted":  0,
                "drift_score":       0.0,
                "drift_detected":    False,
                "feature_report":    [],
                "note":              "Window is empty — no drift computed.",
            }

        # Transpose: feature_name → [values across window]
        feature_map: dict[str, list[float]] = {}
        baseline_keys = list(self.baseline.keys())

        for vec in raw_features:
            if isinstance(vec, list):
                # Anonymous list — map by index to baseline feature order
                for idx, val in enumerate(vec):
                    if idx < len(baseline_keys):
                        key = baseline_keys[idx]
                        feature_map.setdefault(key, []).append(float(val))
            elif isinstance(vec, dict):
                for k, v in vec.items():
                    try:
                        feature_map.setdefault(k, []).append(float(v))
                    except (TypeError, ValueError):
                        pass

        if not feature_map:
            return {
                "window_size":      window.size,
                "features_checked": 0,
                "features_drifted": 0,
                "drift_score":      0.0,
                "drift_detected":   False,
                "feature_report":   [],
                "note":             "Could not extract numeric features.",
            }

        # Run selected detection method per feature
        report    = []
        n_drifted = 0

        for feat, vals in feature_map.items():
            if feat not in self.baseline:
                continue
            if self.method == "ks":
                result = _ks_drift(feat, self.baseline, vals)
            else:
                result = _zscore_drift(feat, self.baseline, vals)
            report.append(result)
            if result["drift_detected"]:
                n_drifted += 1

        n_checked     = len(report)
        drift_score   = round(n_drifted / n_checked, 4) if n_checked else 0.0
        detected      = drift_score >= FEATURE_RATIO
        severity      = get_severity(drift_score) if detected else "NONE"

        return {
            "window_size":       window.size,
            "features_checked":  n_checked,
            "features_drifted":  n_drifted,
            "drift_score":       drift_score,
            "drift_detected":    detected,
            "drift_severity":    severity,
            "feature_report":    report,
        }
