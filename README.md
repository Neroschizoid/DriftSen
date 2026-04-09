# DriftSentinel

A secure real-time MLOps framework with automated drift and data poisoning detection.

## Setup

```bash
conda create -n driftsentinel python=3.10
conda activate driftsentinel
##for windows activate the python enviornment   
pip install -r requirements.txt


## Dataset

This project uses the UNSW-NB15 dataset for network intrusion detection.

Place the following file inside:

data/raw/UNSW_NB15_training-set.csv

The dataset can be downloaded from:
https://research.unsw.edu.au/projects/unsw-nb15-dataset



---

# 🛡 DriftSentinel — Baseline Model Training Report

---

## 1️⃣ Objective

To establish a reliable baseline intrusion detection model using the **UNSW-NB15** dataset for binary classification:

* `0` → Normal traffic
* `1` → Attack traffic

The purpose of this baseline is:

* Provide a deployable ML artifact
* Generate statistical reference distribution (for drift detection)
* Enable real-time inference API integration
* Act as foundation for monitoring layer

---

## 2️⃣ Dataset Overview

**Dataset:** UNSW-NB15 Training Set
**Total Samples:** 82,332
**Total Features:** 45

After preprocessing:

* Dropped: `id`, `attack_cat`
* Target: `label`
* Categorical columns one-hot encoded

Final feature space:
Depends on one-hot expansion (~50–60+ features)

---

## 3️⃣ Preprocessing Pipeline

### Step 1 — Column Removal

Dropped:

* `id` → identifier, non-informative
* `attack_cat` → multi-class target (not used in baseline)

### Step 2 — Target Separation

```python
y = df["label"]
X = df.drop(columns=["label"])
```

### Step 3 — Categorical Encoding

Applied:

```python
pd.get_dummies(X)
```

Encoding applied to:

* proto
* service
* state

This ensures compatibility with tree-based models.

---

## 4️⃣ Train/Test Split

Used:

```python
train_test_split(test_size=0.2, random_state=42)
```

Split ratio:

* 80% Training
* 20% Testing

Why?

* Balanced evaluation
* Prevent data leakage
* Reproducibility via fixed seed

---

## 5️⃣ Model Selection

### Algorithm: RandomForestClassifier

Configuration:

```python
RandomForestClassifier(
    n_estimators=100,
    random_state=42,
    n_jobs=-1
)
```

### Why RandomForest?

* Handles tabular data well
* Robust to noise
* No scaling required
* Resistant to overfitting
* Parallelizable (`n_jobs=-1`)
* Good baseline for security datasets

Deep learning not necessary for this structured dataset.

---

## 6️⃣ Evaluation Metrics

You should have seen output similar to:

```
precision    recall    f1-score
```

Key metrics to report:

* Accuracy
* Precision (attack detection correctness)
* Recall (attack detection coverage)
* F1-score (balance between precision & recall)

In intrusion detection:

⚠ Recall is extremely important
Because missing attacks is costly.

---

## 7️⃣ Model Artifact Generation

After training:

### 1️⃣ Model Saved

```text
data/processed/model.pkl
```

This file contains:

* Trained RandomForest
* Feature importance mapping
* Internal tree ensemble

---

### 2️⃣ Baseline Statistics Generated

```text
data/processed/baseline_stats.json
```

Contains:

```json
{
  "feature_name": {
    "mean": ...,
    "std": ...
  }
}
```

Purpose:

* Reference distribution
* Week 2: Drift detection
* Statistical monitoring
* Detect feature shift in production

This is key for MLOps.

---

## 8️⃣ Model Training Workflow Summary

```
Raw CSV
   ↓
Preprocessing
   ↓
One-hot encoding
   ↓
Train/Test Split
   ↓
RandomForest Training
   ↓
Evaluation
   ↓
model.pkl
baseline_stats.json
```

---

## 9️⃣ DevOps & MLOps Aspects

During training:

✔ Modular preprocessing
✔ Artifact separation (raw vs processed)
✔ Git ignored data & artifacts
✔ Reproducible environment
✔ Explicit dependency versions
✔ Deterministic split (random_state=42)

This is not just ML — this is MLOps discipline.

---

## 🔟 Limitations (Baseline Model)

* No hyperparameter tuning
* No class imbalance handling
* No cross-validation
* No feature selection
* No calibration

This is intentional.

This is baseline.

DriftSentinel focuses on deployment + monitoring.

---
