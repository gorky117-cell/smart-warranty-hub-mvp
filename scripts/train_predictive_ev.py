"""
Train a simple EV battery risk model using synthetic data.
Saves the model to data/ev_battery_model.pkl with feature names.
"""

from __future__ import annotations

import random
from pathlib import Path
from typing import List, Tuple

import joblib
import numpy as np
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.metrics import accuracy_score, roc_auc_score
from sklearn.model_selection import train_test_split

FEATURE_NAMES = [
    "product_type",
    "age_months",
    "daily_km",
    "fast_charge_sessions",
    "deep_discharge_events",
    "max_temp_seen",
    "behaviour_score",
    "care_score",
    "responsiveness_score",
    "region_climate_band",
]


def seed_rows() -> Tuple[np.ndarray, np.ndarray]:
    """Returns small seed patterns."""
    rows = [
        # LOW
        [3, 12, 25, 2, 0, 32, 0.9, 0.9, 0.9, 0],
        [4, 8, 15, 1, 0, 30, 0.85, 0.8, 0.8, 0],
        # MEDIUM
        [3, 24, 45, 6, 1, 36, 0.6, 0.6, 0.6, 1],
        [4, 20, 50, 7, 2, 38, 0.55, 0.6, 0.55, 1],
        # HIGH
        [3, 36, 70, 12, 4, 45, 0.3, 0.3, 0.3, 2],
        [4, 30, 80, 10, 3, 48, 0.25, 0.3, 0.25, 2],
    ]
    labels = [0, 0, 1, 1, 2, 2]
    return np.array(rows, dtype=float), np.array(labels, dtype=int)


def jitter(row: List[float]) -> List[float]:
    pt, age, km, fast, deep, temp, beh, care, resp, climate = row
    age = max(0, random.gauss(age, 4))
    km = max(0, random.gauss(km, 8))
    fast = max(0, int(random.gauss(fast, 2)))
    deep = max(0, int(random.gauss(deep, 1)))
    temp = max(10, random.gauss(temp, 3))
    beh = min(1, max(0, random.gauss(beh, 0.05)))
    care = min(1, max(0, random.gauss(care, 0.05)))
    resp = min(1, max(0, random.gauss(resp, 0.05)))
    climate = int(max(0, min(2, round(random.gauss(climate, 0.2)))))
    return [pt, age, km, fast, deep, temp, beh, care, resp, climate]


def expand(seeds: np.ndarray, labels: np.ndarray, target: int = 1200) -> Tuple[np.ndarray, np.ndarray]:
    rows, labs = [], []
    for _ in range(target):
        i = random.randrange(len(seeds))
        rows.append(jitter(seeds[i].tolist()))
        labs.append(labels[i])
    return np.array(rows, dtype=float), np.array(labs, dtype=int)


def main():
    random.seed(42)
    np.random.seed(42)
    seeds, labels = seed_rows()
    X, y = expand(seeds, labels, target=1200)
    X_train, X_val, y_train, y_val = train_test_split(X, y, test_size=0.2, stratify=y, random_state=42)
    model = GradientBoostingClassifier(random_state=42)
    model.fit(X_train, y_train)
    pred = model.predict(X_val)
    proba = model.predict_proba(X_val)
    acc = accuracy_score(y_val, pred)
    auc = roc_auc_score(y_val, proba, multi_class="ovo")
    out_path = Path(__file__).resolve().parents[1] / "data" / "ev_battery_model.pkl"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump({"model": model, "feature_names": FEATURE_NAMES}, out_path)
    counts = {c: int((y == c).sum()) for c in np.unique(y)}
    print("[EV TRAIN] saved to", out_path)
    print("[EV TRAIN] class balance:", counts)
    print("[EV TRAIN] acc", round(acc, 3), "auc", round(auc, 3))


if __name__ == "__main__":
    main()
