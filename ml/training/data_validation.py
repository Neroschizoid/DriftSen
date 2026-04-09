from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

REQUIRED_COLUMNS = {"label"}


def load_dataset(csv_path: str | Path) -> pd.DataFrame:
    path = Path(csv_path)
    if not path.exists():
        raise FileNotFoundError(f"Dataset not found: {path}")
    return pd.read_csv(path)


def validate_dataframe(df: pd.DataFrame) -> dict:
    if df.empty:
        raise ValueError("Input dataset is empty.")

    missing = REQUIRED_COLUMNS - set(df.columns)
    if missing:
        raise ValueError(f"Missing required columns: {sorted(missing)}")

    if df.columns.duplicated().any():
        dupes = df.columns[df.columns.duplicated()].tolist()
        raise ValueError(f"Duplicate column names detected: {dupes}")

    label_values = set(pd.Series(df["label"]).dropna().unique().tolist())
    if not label_values:
        raise ValueError("Target column 'label' has no valid values.")

    non_binary = {v for v in label_values if v not in (0, 1)}
    if non_binary:
        raise ValueError(
            "Target column 'label' must be binary (0/1). "
            f"Found values: {sorted(non_binary)}"
        )

    return {
        "rows": int(df.shape[0]),
        "columns": int(df.shape[1]),
        "missing_cells": int(df.isna().sum().sum()),
        "label_distribution": df["label"].value_counts().to_dict(),
    }


def run_validation(csv_path: str | Path) -> dict:
    df = load_dataset(csv_path)
    return validate_dataframe(df)


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate training dataset schema and labels.")
    parser.add_argument(
        "--csv-path",
        default="data/raw/UNSW_NB15_training-set.csv",
        help="Path to the training CSV file.",
    )
    args = parser.parse_args()

    report = run_validation(args.csv_path)
    print("Validation passed:")
    for key, value in report.items():
        print(f"- {key}: {value}")


if __name__ == "__main__":
    main()
