from __future__ import annotations

import argparse
import json
from pathlib import Path

import joblib
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, classification_report, f1_score, precision_score, recall_score
from sklearn.model_selection import train_test_split

from data_preprocessing import compute_baseline_stats, preprocess_dataframe
from data_validation import load_dataset, validate_dataframe


def train_pipeline(
    csv_path: str | Path,
    model_out: str | Path,
    stats_out: str | Path,
    test_size: float = 0.2,
    random_state: int = 42,
    n_estimators: int = 100,
) -> dict:
    df = load_dataset(csv_path)
    validation_report = validate_dataframe(df)
    X, y = preprocess_dataframe(df)

    stratify_y = y if y.nunique() > 1 else None
    X_train, X_test, y_train, y_test = train_test_split(
        X,
        y,
        test_size=test_size,
        random_state=random_state,
        stratify=stratify_y,
    )

    model = RandomForestClassifier(
        n_estimators=n_estimators,
        random_state=random_state,
        n_jobs=-1,
    )
    model.fit(X_train, y_train)

    y_pred = model.predict(X_test)
    metrics = {
        "accuracy": float(accuracy_score(y_test, y_pred)),
        "precision": float(precision_score(y_test, y_pred, zero_division=0)),
        "recall": float(recall_score(y_test, y_pred, zero_division=0)),
        "f1": float(f1_score(y_test, y_pred, zero_division=0)),
    }

    model_path = Path(model_out)
    stats_path = Path(stats_out)
    model_path.parent.mkdir(parents=True, exist_ok=True)
    stats_path.parent.mkdir(parents=True, exist_ok=True)

    joblib.dump(model, model_path)
    baseline_stats = compute_baseline_stats(X_train)
    stats_path.write_text(json.dumps(baseline_stats, indent=2))

    report = {
        "validation": validation_report,
        "dataset_rows": int(X.shape[0]),
        "feature_count": int(X.shape[1]),
        "train_rows": int(X_train.shape[0]),
        "test_rows": int(X_test.shape[0]),
        "metrics": metrics,
        "model_path": str(model_path),
        "baseline_stats_path": str(stats_path),
    }

    print("\nTraining complete.")
    print(f"Model: {model_path}")
    print(f"Baseline stats: {stats_path}")
    print(f"Features: {report['feature_count']} | Train/Test: {report['train_rows']}/{report['test_rows']}")
    print(
        "Metrics -> "
        f"accuracy={metrics['accuracy']:.4f}, "
        f"precision={metrics['precision']:.4f}, "
        f"recall={metrics['recall']:.4f}, "
        f"f1={metrics['f1']:.4f}"
    )
    print("\nClassification report:")
    print(classification_report(y_test, y_pred, zero_division=0))
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Train baseline model and generate baseline stats.")
    parser.add_argument("--csv-path", default="data/raw/UNSW_NB15_training-set.csv")
    parser.add_argument("--model-out", default="ml/models/model.pkl")
    parser.add_argument("--stats-out", default="ml/stats/baseline_stats.json")
    parser.add_argument("--test-size", type=float, default=0.2)
    parser.add_argument("--random-state", type=int, default=42)
    parser.add_argument("--n-estimators", type=int, default=100)
    args = parser.parse_args()

    train_pipeline(
        csv_path=args.csv_path,
        model_out=args.model_out,
        stats_out=args.stats_out,
        test_size=args.test_size,
        random_state=args.random_state,
        n_estimators=args.n_estimators,
    )


if __name__ == "__main__":
    main()
