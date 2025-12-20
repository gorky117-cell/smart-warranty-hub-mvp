"""
Train a predictive model using behaviour + usage features.
Steps:
- Load seeds from data/sample_training_behaviour.csv if present.
- Expand to a larger synthetic dataset with noise (~6000 rows).
- Train GradientBoostingClassifier.
- Save to data/predictive_model.pkl with feature names.
- Print class balance and accuracy/AUC.
"""

from __future__ import annotations

from pathlib import Path
import random
from typing import List, Tuple

import joblib
import numpy as np
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.metrics import accuracy_score, roc_auc_score
from sklearn.model_selection import train_test_split

FEATURE_NAMES = [
    "product_type",
    "age_months",
    "usage_hours_per_day",
    "error_count",
    "failure_count",
    "maintenance_count",
    "behaviour_score",
    "care_score",
    "responsiveness_score",
    "region_code",
    "climate_band",
    "power_quality_band",
]

SEED_PATH = Path(__file__).resolve().parents[1] / "data" / "sample_training_behaviour.csv"
FALLBACK_ROWS = [
    [0,4,1.5,0,0,2,0.9,0.9,0.9,0],
    [0,8,2.0,1,0,2,0.85,0.9,0.8,0],
    [1,6,1.0,0,0,1,0.95,0.95,0.9,0],
    [2,10,2.5,1,0,2,0.88,0.9,0.85,0],
    [1,3,0.8,0,0,1,0.9,0.85,0.9,0],
    [0,18,3.5,3,0,1,0.6,0.6,0.5,1],
    [0,24,4.0,4,1,1,0.55,0.6,0.5,1],
    [1,20,3.0,2,0,0,0.6,0.55,0.5,1],
    [2,22,4.5,3,0,1,0.65,0.6,0.55,1],
    [1,30,2.5,3,0,0,0.5,0.55,0.45,1],
    [0,40,6.0,10,2,0,0.3,0.2,0.2,2],
    [0,14,5.5,9,1,0,0.25,0.3,0.2,2],
    [1,48,4.5,8,2,0,0.35,0.3,0.25,2],
    [2,36,7.0,6,1,0,0.3,0.25,0.2,2],
    [2,18,5.0,8,1,0,0.2,0.25,0.2,2],
]


def parse_seed_line(line: str) -> Tuple[List[float], int] | None:
    line = line.strip()
    if not line or line.startswith("#"):
        return None
    parts = [p.strip() for p in line.split(",")]
    # Accept either full feature length or original 10-feature rows (pad missing bands with zeros)
    if len(parts) == len(FEATURE_NAMES) + 1:
        feature_count = len(FEATURE_NAMES)
    elif len(parts) == 10 + 1:
        feature_count = 10
    else:
        print(f"[WARN] Skipping line with wrong column count: {line}")
        return None
    try:
        feats = [float(parts[i]) for i in range(feature_count)]
        label = int(parts[-1])
        if feature_count == 10:
            # pad missing region/climate/power bands with zeros
            feats.extend([0.0, 0.0, 0.0])
    except Exception:
        print(f"[WARN] Skipping unparsable line: {line}")
        return None
    return feats, label


def load_seeds(path: Path) -> Tuple[np.ndarray, np.ndarray]:
    rows, labels = [], []
    if not path.exists():
        print(f"[WARN] Seed file not found: {path}")
        rows = [r[:] + [0.0,0.0,0.0] if len(r)==10 else r for r in FALLBACK_ROWS]
        labels = [int(r[-1]) for r in rows]
        rows = [r[:-1] if len(r)==len(FEATURE_NAMES)+1 else r for r in rows]
        return np.array(rows, dtype=float), np.array(labels, dtype=int)
    lines = [ln for ln in path.read_text().splitlines() if ln.strip()]
    for line in lines:
        parsed = parse_seed_line(line)
        if parsed:
            feats, lab = parsed
            rows.append(feats)
            labels.append(lab)
    if not rows:
        print(f"[WARN] Seed file exists but no valid rows parsed: {path}")
        rows = [r[:] + [0.0,0.0,0.0] if len(r)==10 else r for r in FALLBACK_ROWS]
        labels = [int(r[-1]) for r in FALLBACK_ROWS]
        rows = [r[:-1] if len(r)==len(FEATURE_NAMES)+1 else r for r in rows]
    return np.array(rows, dtype=float), np.array(labels, dtype=int)


def jitter_seed(seed_feats: List[float]) -> List[float]:
    (
        pt,
        age,
        usage,
        err,
        fail,
        maint,
        beh,
        care,
        resp,
        region_code,
        climate_band,
        power_quality_band,
    ) = seed_feats
    age = max(0, random.gauss(age, 2))
    usage = max(0, random.gauss(usage, 0.5))
    err = max(0, int(random.gauss(err, 1)))
    fail = max(0, int(random.gauss(fail, 0.5)))
    maint = max(0, int(random.gauss(maint, 0.5)))
    beh = min(1, max(0, random.gauss(beh, 0.05)))
    care = min(1, max(0, random.gauss(care, 0.05)))
    resp = min(1, max(0, random.gauss(resp, 0.05)))
    # add bounded noise to bands
    region_code = int(max(0, min(3, round(random.gauss(region_code, 0.3)))))
    climate_band = int(max(0, min(2, round(random.gauss(climate_band, 0.3)))))
    power_quality_band = int(max(0, min(2, round(random.gauss(power_quality_band, 0.3)))))
    return [pt, age, usage, err, fail, maint, beh, care, resp, region_code, climate_band, power_quality_band]


def expand_dataset(seeds: np.ndarray, labels: np.ndarray, target_size: int = 1500) -> Tuple[np.ndarray, np.ndarray]:
    if seeds.size == 0:
        return seeds, labels
    rows, labs = [], []
    for _ in range(target_size):
        idx = random.randrange(len(seeds))
        base = seeds[idx].tolist()
        lab = int(labels[idx])
        rows.append(jitter_seed(base))
        labs.append(lab)
    return np.array(rows, dtype=float), np.array(labs, dtype=int)


def main():
    import time
    start_time = time.time()
    print("[TRAIN] Training started...")
    print(f"[TRAIN] Looking for seeds at: {SEED_PATH}")
    random.seed(42)
    np.random.seed(42)
    seeds, seed_labels = load_seeds(SEED_PATH)
    if seeds.size == 0:
        raise SystemExit(f"No seed data found at {SEED_PATH}")
    # Ensure at least two classes
    unique = np.unique(seed_labels)
    if unique.size < 2:
        # duplicate a few rows and flip labels to create another class
        extra_rows = []
        extra_labels = []
        for i in range(min(3, len(seeds))):
            extra_rows.append(seeds[i])
            extra_labels.append((seed_labels[i] + 1) % 3)
        seeds = np.vstack([seeds, np.array(extra_rows)])
        seed_labels = np.concatenate([seed_labels, np.array(extra_labels, dtype=int)])
    X, y = expand_dataset(seeds, seed_labels, target_size=1500)
    X_train, X_val, y_train, y_val = train_test_split(X, y, test_size=0.2, stratify=y, random_state=42)
    model = GradientBoostingClassifier(n_estimators=80, max_depth=2, random_state=42)
    if time.time() - start_time > 20:
        print("Training aborted: exceeded 20 seconds before fitting.")
        return
    model.fit(X_train, y_train)
    val_pred = model.predict(X_val)
    val_proba = model.predict_proba(X_val)
    acc = accuracy_score(y_val, val_pred)
    auc = roc_auc_score(y_val, val_proba, multi_class="ovo")
    out_path = Path(__file__).resolve().parents[1] / "data" / "predictive_model.pkl"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump({"model": model, "feature_names": FEATURE_NAMES}, out_path)
    print(f"Saved model to {out_path}")
    counts = {c: int((y == c).sum()) for c in np.unique(y)}
    print(f"Class balance: {counts}")
    print(f"Validation accuracy: {acc:.3f} | AUC (OVO): {auc:.3f}")
    print("[TRAIN] Training finished")


if __name__ == "__main__":
    main()
