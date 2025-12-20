from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import joblib


EV_FEATURE_NAMES = [
    "product_type",  # 3 = EV car, 4 = EV 2W
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


@dataclass
class EVBatteryScore:
    risk_label: str
    risk_score: float
    proba: Dict[str, float]
    reasons: List[str]
    suggestions: List[str]


class EVBatteryModel:
    def __init__(self, path: Optional[Path] = None):
        self.path = path or Path(__file__).resolve().parents[2] / "data" / "ev_battery_model.pkl"
        self.model = None
        self.feature_names = EV_FEATURE_NAMES
        self.error: Optional[str] = None


def build_features_from_db(db, user_id: str, warranty_id: str):
    # Minimal wrapper pulling latest telemetry if present; fallback defaults.
    from ..storage import store
    events = store.get_telemetry(user_id, warranty_id)
    # Defaults aligned with EVBatteryRequest defaults
    data = {
        "product_type": 3,
        "age_months": 12,
        "daily_km": 40,
        "fast_charge_sessions": 4,
        "deep_discharge_events": 1,
        "max_temp_seen": 32,
        "behaviour_score": 0.5,
        "care_score": 0.5,
        "responsiveness_score": 0.5,
        "region_climate_band": 1,
    }
    # Optional enrichment from telemetry payloads
    for ev in events:
        if ev.event_type == "usage":
            data["daily_km"] = ev.payload.get("daily_km", data["daily_km"])
        if ev.event_type == "failure":
            data["deep_discharge_events"] = ev.payload.get("deep_discharge_events", data["deep_discharge_events"])
        if ev.event_type == "maintenance":
            data["max_temp_seen"] = ev.payload.get("max_temp_seen", data["max_temp_seen"])
    return data

    def load(self):
        if self.model or self.error:
            return self
        if not self.path.exists():
            self.error = "EV model missing"
            return self
        try:
            stored = joblib.load(self.path)
            if isinstance(stored, dict):
                self.model = stored.get("model")
                self.feature_names = stored.get("feature_names", EV_FEATURE_NAMES)
            else:
                self.model = stored
        except Exception as exc:
            self.error = str(exc)
        return self

    def predict(self, feats: List[float]) -> Tuple[Optional[str], Optional[float], Dict[str, float]]:
        self.load()
        if not self.model:
            return None, None, {}
        try:
            if hasattr(self.model, "predict_proba"):
                proba = self.model.predict_proba([feats])[0]
                labels = ["LOW", "MEDIUM", "HIGH"]
                idx = int(proba.argmax()) if hasattr(proba, "argmax") else int(max(range(len(proba)), key=lambda i: proba[i]))
                label = labels[idx] if idx < len(labels) else "LOW"
                proba_map = {labels[i]: float(proba[i]) for i in range(min(len(labels), len(proba)))}
                return label, float(proba[idx]), proba_map
            pred = self.model.predict([feats])[0]
            labels = ["LOW", "MEDIUM", "HIGH"]
            label = labels[int(pred)] if int(pred) < len(labels) else "LOW"
            return label, 1.0, {}
        except Exception as exc:
            self.error = str(exc)
            return None, None, {}


ev_battery_model = EVBatteryModel()


def _heuristic(features: Dict[str, float]) -> EVBatteryScore:
    age = features.get("age_months", 0)
    daily_km = features.get("daily_km", 0)
    fast = features.get("fast_charge_sessions", 0)
    deep = features.get("deep_discharge_events", 0)
    temp = features.get("max_temp_seen", 25)
    beh = features.get("behaviour_score", 0.5)
    care = features.get("care_score", 0.5)
    resp = features.get("responsiveness_score", 0.5)
    climate = features.get("region_climate_band", 0)

    score = 0.2
    reasons = []
    if daily_km > 60:
        score += 0.2
        reasons.append("High daily kilometres.")
    if fast > 8:
        score += 0.2
        reasons.append("Frequent fast charging.")
    if deep > 2:
        score += 0.2
        reasons.append("Battery often drops below 10%.")
    if temp > 40 or climate >= 2:
        score += 0.15
        reasons.append("Used in hot conditions.")
    if beh < 0.4 or care < 0.4:
        score += 0.1
        reasons.append("Limited care habits.")

    label = "LOW"
    if score >= 0.66:
        label = "HIGH"
    elif score >= 0.4:
        label = "MEDIUM"
    suggestions = [
        "Avoid fast charging unless you need a quick top-up.",
        "Try not to let the battery drop below 10%.",
        "Parking in shade helps battery health.",
    ]
    return EVBatteryScore(label, round(score, 3), {}, reasons or ["Light usage so far."], suggestions)


def score_ev_battery(features: Dict[str, float]) -> EVBatteryScore:
    vec = [
        features.get("product_type", 3),
        features.get("age_months", 0),
        features.get("daily_km", 0),
        features.get("fast_charge_sessions", 0),
        features.get("deep_discharge_events", 0),
        features.get("max_temp_seen", 25),
        features.get("behaviour_score", 0.5),
        features.get("care_score", 0.5),
        features.get("responsiveness_score", 0.5),
        features.get("region_climate_band", 0),
    ]
    label, prob, proba = ev_battery_model.predict(vec)
    if not label or prob is None:
        return _heuristic(features)

    reasons = []
    if features.get("daily_km", 0) > 60:
        reasons.append("High daily kilometres.")
    if features.get("fast_charge_sessions", 0) > 8:
        reasons.append("Frequent fast charging.")
    if features.get("deep_discharge_events", 0) > 2:
        reasons.append("Battery often drops below 10%.")
    if features.get("max_temp_seen", 0) > 40 or features.get("region_climate_band", 0) >= 2:
        reasons.append("Hot conditions may stress the battery.")
    if features.get("behaviour_score", 0.5) < 0.4:
        reasons.append("Care habits could be improved.")
    suggestions = [
        "Avoid fast charging unless needed.",
        "Keep charge between 20% and 80% for daily use.",
        "Park in shade to reduce heat.",
    ]
    return EVBatteryScore(
        risk_label=label,
        risk_score=round(float(prob), 3),
        proba=proba,
        reasons=reasons[:4] or ["Driving pattern looks healthy."],
        suggestions=suggestions,
    )
