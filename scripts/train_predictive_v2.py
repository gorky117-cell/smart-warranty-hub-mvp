"""
Train predictive model v2 with richer synthetic signals:
- usage / errors / failures / maintenance
- behaviour / care / responsiveness
- region/climate one-hots
- OEM factors, peer reviews, symptom search patterns
"""

from pathlib import Path
import random

import joblib
import numpy as np
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import roc_auc_score

CLIMATES = ["hot", "humid", "dry", "cold", "coastal"]
REGIONS = ["na", "eu", "apac", "latam", "mea"]
COMPONENTS = ["motor", "drum", "bearing", "pump", "seal"]


def one_hot(value, vocab):
    return [1 if value == v else 0 for v in vocab]


def generate_row():
    region = random.choice(REGIONS)
    climate = random.choice(CLIMATES)
    usage = max(0, random.gauss(120, 60))
    errors = max(0, int(random.gauss(1.2, 1.1)))
    failures = max(0, int(random.gauss(0.3, 0.6)))
    maintenance = max(0, int(random.gauss(1.2, 0.8)))
    behaviour = min(max(random.gauss(0.55, 0.2), 0), 1)
    care = min(max(random.gauss(0.55, 0.2), 0), 1)
    responsiveness = min(max(random.gauss(0.55, 0.2), 0), 1)
    nudges_shown = max(1, int(random.gauss(3, 2)))
    nudges_acted = max(0, int(nudges_shown * random.uniform(0.2, 0.8) * responsiveness))
    nudges_ignored = max(0, nudges_shown - nudges_acted)
    avg_rating = max(1.0, min(5.0, random.gauss(4.0, 0.5)))
    review_sentiment = random.uniform(0.2, 0.9)
    failure_keyword_count = max(0, int(random.gauss(1.5, 1.0)))
    search_count = max(0, int(random.gauss(2, 2)))
    unresolved_search = max(0, search_count - random.randint(0, search_count))
    component_focus = random.choice(COMPONENTS)
    component_vec = one_hot(component_focus, COMPONENTS)
    oem_risk_factor = max(0, min(1, random.gauss(0.3, 0.2)))
    brand_reliability = max(0, min(1, random.gauss(0.6, 0.2)))
    months_used = max(0, random.gauss(18, 10))
    days_to_expiry = max(-400, int(random.gauss(200, 150)))
    is_out = 1 if days_to_expiry < 0 else 0

    base_prob = 0.15
    base_prob += 0.004 * usage + 0.1 * errors + 0.25 * failures - 0.05 * maintenance
    base_prob += 0.2 * (1 - behaviour) + 0.15 * (1 - care) + 0.1 * (1 - responsiveness)
    base_prob += 0.1 * (1 - brand_reliability) + 0.1 * oem_risk_factor
    base_prob += 0.05 * failure_keyword_count + 0.05 * unresolved_search
    base_prob -= 0.1 * (nudges_acted / max(nudges_shown, 1))
    base_prob += 0.1 * is_out
    base_prob = min(max(base_prob, 0), 1)
    label = 1 if random.random() < base_prob else 0

    features = [
        usage,
        errors,
        failures,
        maintenance,
        months_used,
        days_to_expiry,
        is_out,
        behaviour,
        care,
        responsiveness,
        nudges_shown,
        nudges_acted,
        nudges_ignored,
        avg_rating,
        review_sentiment,
        failure_keyword_count,
        search_count,
        unresolved_search,
        oem_risk_factor,
        brand_reliability,
    ] + one_hot(region, REGIONS) + one_hot(climate, CLIMATES) + component_vec

    return features, label


def build_dataset(n=2000):
    rows, labels = [], []
    for _ in range(n):
        f, y = generate_row()
        rows.append(f)
        labels.append(y)
    return np.array(rows), np.array(labels)


def main():
    X, y = build_dataset()
    X_train, X_val, y_train, y_val = train_test_split(X, y, test_size=0.2, stratify=y, random_state=42)
    model = GradientBoostingClassifier()
    model.fit(X_train, y_train)
    val_pred = model.predict_proba(X_val)[:, 1]
    auc = roc_auc_score(y_val, val_pred)
    feature_names = [
        "usage_hours","errors","failures","maintenance",
        "months_used","days_to_expiry","is_out_of_coverage",
        "behaviour_score","care_score","response_speed_score",
        "nudges_shown","nudges_acted","nudges_ignored",
        "avg_rating","review_sentiment","failure_keyword_count",
        "search_count","unresolved_search_count","oem_risk_factor","brand_reliability_score",
    ] + [f"region_{r}" for r in REGIONS] + [f"climate_{c}" for c in CLIMATES] + [f"component_{c}" for c in COMPONENTS]
    out_path = Path(__file__).resolve().parents[1] / "data" / "predictive_model.pkl"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump({"model": model, "auc": auc, "feature_names": feature_names}, out_path)
    print(f"Saved model to {out_path} (val AUC={auc:.3f})")


if __name__ == "__main__":
    main()
