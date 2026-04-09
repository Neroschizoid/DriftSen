from pathlib import Path
import sys

import pandas as pd
import pytest

TRAINING_DIR = Path(__file__).resolve().parents[1] / "ml" / "training"
sys.path.insert(0, str(TRAINING_DIR))

from data_preprocessing import compute_baseline_stats, preprocess_dataframe  # noqa: E402
from data_validation import validate_dataframe  # noqa: E402


def test_validate_dataframe_accepts_binary_label():
    df = pd.DataFrame(
        {
            "id": [1, 2],
            "dur": [0.1, 0.2],
            "label": [0, 1],
        }
    )
    report = validate_dataframe(df)
    assert report["rows"] == 2
    assert report["columns"] == 3


def test_validate_dataframe_rejects_non_binary_label():
    df = pd.DataFrame({"dur": [0.1, 0.2], "label": [0, 2]})
    with pytest.raises(ValueError, match="binary"):
        validate_dataframe(df)


def test_preprocess_dataframe_encodes_and_drops_columns():
    df = pd.DataFrame(
        {
            "id": [1, 2],
            "attack_cat": ["DoS", "Normal"],
            "proto": ["tcp", "udp"],
            "dur": [1.0, 2.0],
            "label": [0, 1],
        }
    )
    X, y = preprocess_dataframe(df)
    assert "id" not in X.columns
    assert "attack_cat" not in X.columns
    assert any(col.startswith("proto_") for col in X.columns)
    assert list(y) == [0, 1]


def test_compute_baseline_stats_returns_mean_and_std():
    X = pd.DataFrame({"dur": [1.0, 2.0, 3.0], "rate": [10.0, 10.0, 10.0]})
    stats = compute_baseline_stats(X)
    assert "dur" in stats and "rate" in stats
    assert set(stats["dur"].keys()) == {"mean", "std"}
    assert stats["dur"]["mean"] == pytest.approx(2.0)
