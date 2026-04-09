from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

DROP_COLUMNS = ("id", "attack_cat")


def preprocess_dataframe(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.Series]:
    if "label" not in df.columns:
        raise ValueError("Target column 'label' is required.")

    y = df["label"].astype(int)
    X = df.drop(columns=["label"], errors="ignore")
    X = X.drop(columns=[c for c in DROP_COLUMNS if c in X.columns], errors="ignore")

    categorical_cols = X.select_dtypes(include=["object", "category", "bool"]).columns
    if len(categorical_cols) > 0:
        X = pd.get_dummies(X, columns=list(categorical_cols), dtype=float)

    X = X.replace([np.inf, -np.inf], np.nan).fillna(0.0)
    X = X.apply(pd.to_numeric, errors="coerce").fillna(0.0)
    X = X.reindex(sorted(X.columns), axis=1)
    return X, y


def align_to_feature_order(X: pd.DataFrame, feature_order: list[str]) -> pd.DataFrame:
    return X.reindex(columns=feature_order, fill_value=0.0)


def compute_baseline_stats(X: pd.DataFrame) -> dict:
    if X.empty:
        raise ValueError("Cannot compute baseline stats on an empty feature matrix.")

    stats = {}
    for col in X.columns:
        series = pd.to_numeric(X[col], errors="coerce").fillna(0.0)
        stats[col] = {"mean": float(series.mean()), "std": float(series.std(ddof=1) or 0.0)}
    return stats


def main() -> None:
    parser = argparse.ArgumentParser(description="Preview preprocessing and baseline stats.")
    parser.add_argument("--csv-path", default="data/raw/UNSW_NB15_training-set.csv")
    parser.add_argument("--preview-out", default="")
    args = parser.parse_args()

    df = pd.read_csv(args.csv_path)
    X, y = preprocess_dataframe(df)
    stats = compute_baseline_stats(X)

    print(f"Rows: {len(X)} | Features: {len(X.columns)} | Label classes: {sorted(y.unique().tolist())}")
    print(f"First 5 features: {list(X.columns[:5])}")
    if args.preview_out:
        out = Path(args.preview_out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(stats, indent=2))
        print(f"Wrote baseline preview: {out}")


if __name__ == "__main__":
    main()
