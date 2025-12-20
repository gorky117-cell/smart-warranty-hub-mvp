from collections import Counter
from datetime import datetime, timedelta
import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import joblib

from ..models import PredictiveScore, TelemetryEvent
from ..storage import store
from ..db import SessionLocal
from ..db_models import BehaviourProfile, NudgeEvents, PeerReviewSignals, SymptomSearch, WarrantyDB
from . import behaviour as behaviour_service

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

_loaded_model = None
_model_meta = None
_model_error = None
logger = logging.getLogger(__name__)


class PredictiveModel:
    def __init__(self, model_path: Optional[Path] = None):
        self.model_path = model_path or Path(__file__).resolve().parents[2] / "data" / "predictive_model.pkl"
        self.model = None
        self.feature_names = FEATURE_NAMES
        self.error: Optional[str] = None

    def load(self):
        if self.model or self.error:
            return self
        if not self.model_path.exists():
            self.error = "Model file missing"
            return self
        try:
            stored = joblib.load(self.model_path)
            if isinstance(stored, dict):
                self.model = stored.get("model")
                self.feature_names = stored.get("feature_names", FEATURE_NAMES)
            else:
                self.model = stored
        except Exception as exc:  # pragma: no cover
            self.error = str(exc)
        return self

    def predict(self, features: List[float]) -> Tuple[Optional[str], Optional[float], Optional[List[float]]]:
        self.load()
        if not self.model:
            return None, None, None
        try:
            if hasattr(self.model, "predict_proba"):
                proba = self.model.predict_proba([features])[0]
                idx = int(proba.argmax()) if hasattr(proba, "argmax") else int(max(range(len(proba)), key=lambda i: proba[i]))
                labels = ["LOW", "MEDIUM", "HIGH"]
                label = labels[idx] if idx < len(labels) else "LOW"
                score = float(proba[idx])
                return label, score, proba.tolist() if hasattr(proba, "tolist") else list(proba)
            pred = self.model.predict([features])[0]
            labels = ["LOW", "MEDIUM", "HIGH"]
            label = labels[int(pred)] if isinstance(pred, (int, float)) and int(pred) < len(labels) else "LOW"
            return label, 1.0, None
        except Exception as exc:  # pragma: no cover
            self.error = str(exc)
            return None, None, None

    def explain_reasons(self, features: List[float], risk_label: Optional[str]) -> List[str]:
        if not features:
            return ["Not enough data yet."]
        _, age, usage, errors, failures, maintenance, behaviour, care, resp, region_code, climate_band, _ = features
        reasons: List[str] = []
        if age > 30:
            reasons.append("Device is older and may see more wear.")
        elif age < 12:
            reasons.append("Device is relatively new.")
        if usage > 4:
            reasons.append("High daily use.")
        else:
            reasons.append("Light to moderate daily use.")
        if errors >= 3:
            reasons.append("Multiple errors recorded.")
        if failures >= 1:
            reasons.append("Past breakdowns detected.")
        if maintenance == 0:
            reasons.append("No maintenance recorded.")
        if behaviour < 0.4 or care < 0.4 or resp < 0.4:
            reasons.append("Habits suggest limited care or responsiveness.")
        if behaviour > 0.7 and care > 0.7 and resp > 0.7:
            reasons.append("Good care habits help keep risk low.")
        return reasons[:4] or ["Data looks healthy so far."]


predictive_model = PredictiveModel()


def aggregate_failure_reasons(events: List[TelemetryEvent]) -> List[str]:
    reasons: Counter = Counter()
    for ev in events:
        if ev.event_type == "error":
            code = ev.payload.get("code") or ev.payload.get("message") or "unknown_error"
            reasons[code] += 1
        if ev.event_type == "failure":
            reason = ev.payload.get("reason") or "unspecified_failure"
            reasons[reason] += 2
    top = [item for item, _ in reasons.most_common(5)]
    return top


def compute_behaviour_risk_signal(
    user_id: str, warranty_id: str, window_days: int = 30, max_events: int = 50
) -> Dict[str, object]:
    """
    Inspect recent telemetry for a (user, warranty) pair and derive a simple behaviour delta.
    Looks at usage hours and error burden to nudge the risk score up/down.
    """
    events = store.get_telemetry(user_id, warranty_id)
    if not events:
        return {"behaviour_risk_delta": 0.0, "reasons": []}
    now = datetime.utcnow()
    cutoff = now - timedelta(days=window_days)
    recent = [ev for ev in events if getattr(ev, "timestamp", now) >= cutoff]
    recent = sorted(recent, key=lambda e: getattr(e, "timestamp", now))[-max_events:]

    usage_events = [ev for ev in recent if ev.event_type == "usage"]
    error_events = [ev for ev in recent if ev.event_type == "error"]
    last_usage_events = usage_events[-10:] if usage_events else []

    hours_list = [float((ev.payload or {}).get("hours", 0) or 0.0) for ev in last_usage_events]
    total_hours = sum(hours_list)
    last_hours = hours_list[-1] if hours_list else 0.0
    avg_hours = (total_hours / len(hours_list)) if hours_list else 0.0

    last_errors = 0
    if last_usage_events:
        last_payload = (last_usage_events[-1].payload or {})
        last_errors = int(last_payload.get("errors", 0) or 0)
    error_burden = last_errors + len(error_events[-5:])

    # Emphasise the latest usage but keep a small eye on average
    if last_hours < 10:
        usage_intensity = "low"
    elif avg_hours < 500:
        usage_intensity = "medium"
    else:
        usage_intensity = "high"

    error_level = "low" if error_burden == 0 else "medium" if error_burden <= 3 else "high"

    delta = 0.0
    reasons: List[str] = []

    if usage_intensity == "low":
        delta -= 0.12
        reasons.append(f"Light recent usage ({int(last_hours)} hrs last event)")
    elif usage_intensity == "medium":
        delta += 0.05
        reasons.append(f"Moderate usage ({int(avg_hours)} hrs avg recent)")
    else:
        delta += 0.18
        reasons.append(f"Heavy use ({int(total_hours)} hrs recent window)")

    if error_level == "low":
        delta -= 0.02
    elif error_level == "medium":
        delta += 0.08
        reasons.append(f"Some errors recorded ({error_burden})")
    else:
        delta += 0.2
        reasons.append(f"Multiple recent errors ({error_burden})")

    delta = max(-0.25, min(0.25, delta))

    return {
        "usage_intensity": usage_intensity,
        "error_burden": error_burden,
        "behaviour_risk_delta": delta,
        "reasons": reasons,
        "hours_window": total_hours,
    }


def derive_score(events: List[TelemetryEvent]) -> Tuple[float, List[str]]:
    score = 0.2  # base
    reasons: List[str] = []
    usage_hours = 0
    errors = 0
    failures = 0
    maintenance = 0

    for ev in events:
        if ev.event_type == "usage":
            usage_hours += ev.payload.get("hours", 0)
        if ev.event_type == "error":
            errors += 1
        if ev.event_type == "failure":
            failures += 1
        if ev.event_type == "maintenance":
            maintenance += 1

    if usage_hours > 100:
        score += 0.15
        reasons.append("High usage hours")
    if errors:
        bump = min(0.05 * errors, 0.3)
        score += bump
        reasons.append(f"{errors} error events")
    if failures:
        bump = min(0.2 * failures, 0.4)
        score += bump
        reasons.append(f"{failures} recorded failures")
    if maintenance:
        score -= min(0.03 * maintenance, 0.15)
        reasons.append("Recent maintenance lowers risk")

    score = max(0.0, min(score, 1.0))
    return score, reasons


def suggest_questions(events: List[TelemetryEvent]) -> List[str]:
    # Simple question generator for missing context
    seen = {ev.event_type for ev in events}
    questions: List[str] = []
    if "maintenance" not in seen:
        questions.append("When was the last maintenance or cleaning performed?")
    if "error" in seen and len(events) > 0:
        questions.append("Have you noticed specific conditions when errors appear (load, temperature, firmware)?")
    if "usage" not in seen:
        questions.append("How many hours per day/week do you use the product?")
    questions.append("Any unusual noises, smells, or performance drops recently?")
    return questions


def _behaviour_features(user_id: str, product_type: Optional[str], warranty_id: Optional[str]) -> Tuple[float, float, float]:
    try:
        return behaviour_service.get_profile_safe(user_id, product_type, warranty_id)
    except Exception:
        return 0.5, 0.5, 0.5


def _nudge_features(user_id: str, warranty_id: str) -> Tuple[int, int, int, float]:
    try:
        with SessionLocal() as db:
            events = db.query(NudgeEvents).filter_by(user_id=user_id, warranty_id=warranty_id).all()
            shown = len(events)
            acted = sum(1 for e in events if e.acted_at)
            ignored = sum(1 for e in events if e.ignored_at and not e.acted_at)
            rate = acted / shown if shown else 0.0
            return shown, acted, ignored, rate
    except Exception:
        return 0, 0, 0, 0.0


def _peer_review_features(warranty_id: str, brand: str | None, model: str | None) -> Tuple[float, float, int]:
    try:
        with SessionLocal() as db:
            rec = db.query(PeerReviewSignals).filter_by(warranty_id=warranty_id).first()
            if not rec and (brand or model):
                rec = (
                    db.query(PeerReviewSignals)
                    .filter_by(brand=brand or "", model=model or "")
                    .order_by(PeerReviewSignals.last_updated_at.desc())
                    .first()
                )
            if rec:
                kw_count = len(rec.failure_keywords or [])
                return rec.avg_rating or 0.0, rec.review_sentiment or 0.0, kw_count
    except Exception:
        pass
    return 0.0, 0.0, 0


def _search_features(user_id: str, warranty_id: str) -> Tuple[int, int, Dict[str, int]]:
    try:
        with SessionLocal() as db:
            searches = db.query(SymptomSearch).filter_by(user_id=user_id, warranty_id=warranty_id).all()
            count = len(searches)
            unresolved = sum(1 for s in searches if not s.matched_component)
            comp_counts: Dict[str, int] = {}
            for s in searches:
                comp = s.matched_component or "other"
                comp_counts[comp] = comp_counts.get(comp, 0) + 1
            return count, unresolved, comp_counts
    except Exception:
        return 0, 0, {}


def _map_str_to_int(val: Optional[str], default: int = 0, vocab: Optional[List[str]] = None) -> int:
    if val is None:
        return default
    if isinstance(val, (int, float)):
        return int(val)
    if isinstance(val, str) and val.isdigit():
        return int(val)
    if vocab:
        try:
            return vocab.index(val)
        except ValueError:
            return default
    return default


def _product_type_code(label: Optional[str]) -> float:
    if label is None:
        return 0.0
    name = str(label).lower()
    if "fridge" in name or name == "refrigerator":
        return 1.0
    if "ac" in name or "air" in name:
        return 2.0
    if name.isdigit():
        try:
            return float(int(name))
        except Exception:
            return 0.0
    return 0.0


def build_feature_vector(
    user_id: str,
    warranty_id: str,
    product_type_override: Optional[str] = None,
) -> Tuple[List[float], List[str], Dict[str, float]]:
    """Builds feature vector in the exact order of FEATURE_NAMES."""
    warranty = store.warranties.get(warranty_id)
    events = store.get_telemetry(user_id, warranty_id)

    product_type_label = product_type_override
    if not product_type_label and warranty and getattr(warranty, "product_name", None):
        product_type_label = warranty.product_name

    product_type = _product_type_code(product_type_label)

    # age
    age_months = 0.0
    if warranty and getattr(warranty, "purchase_date", None):
        try:
            delta = datetime.utcnow().date() - warranty.purchase_date
            age_months = max(0.0, delta.days / 30.0)
        except Exception:
            age_months = 0.0

    usage_hours = sum(ev.payload.get("hours", 0) for ev in events if ev.event_type == "usage")
    usage_events = len([ev for ev in events if ev.event_type == "usage"])
    usage_hours_per_day = usage_hours / max(1, usage_events)
    error_count = sum(1 for ev in events if ev.event_type == "error")
    failure_count = sum(1 for ev in events if ev.event_type == "failure")
    maintenance_count = sum(1 for ev in events if ev.event_type == "maintenance")

    behaviour_score, care_score, responsiveness_score = _behaviour_features(
        user_id, product_type_label, warranty_id
    )

    region_code = _map_str_to_int(getattr(warranty, "region_code", None), 0)
    climate_band = _map_str_to_int(getattr(warranty, "climate_zone", None), 0, ["hot", "humid", "dry", "cold", "coastal"])
    power_quality_band = _map_str_to_int(getattr(warranty, "power_quality_band", None), 0)

    vec = [
        product_type,
        age_months,
        usage_hours_per_day,
        error_count,
        failure_count,
        maintenance_count,
        behaviour_score,
        care_score,
        responsiveness_score,
        region_code,
        climate_band,
        power_quality_band,
    ]

    # expiry helper (not part of feature vector)
    days_left = None
    if warranty and getattr(warranty, "expiry_date", None):
        try:
            exp_dt = warranty.expiry_date
            today = datetime.utcnow().date()
            days_left = max(0, (exp_dt.date() if hasattr(exp_dt, "date") else exp_dt) - today).days
        except Exception:
            days_left = None

    extras = {
        "usage_hours": usage_hours,
        "error_count": error_count,
        "failure_count": failure_count,
        "maintenance_count": maintenance_count,
        "product_type_label": product_type_label,
        "days_left": days_left,
    }
    return vec, FEATURE_NAMES, extras


def score_warranty(user_id: str, warranty_id: str, product_type: Optional[str] = None) -> Dict[str, object]:
    """Return structured predictive output for API/ UI.

    Considers: product type, age, usage hours, error/failure/maintenance counts,
    behaviour profile scores, region/climate/power bands, and a behaviour delta
    derived from recent telemetry usage + errors.
    """
    vec, feat_names, extras = build_feature_vector(user_id, warranty_id, product_type)
    label, score_prob, proba = predictive_model.predict(vec)
    reasons: List[str] = []
    proba_map: Dict[str, float] = {}
    if proba:
        labels = ["LOW", "MEDIUM", "HIGH"]
        proba_map = {labels[i]: float(proba[i]) for i in range(min(len(labels), len(proba)))}
    # If model missing or failed, graceful unknown
    if not label and predictive_model.error:
        return {
            "risk_label": "UNKNOWN",
            "risk_score": 0.5,
            "proba": {},
            "reasons": ["Predictive engine not ready yet."],
            "base_risk_score": 0.5,
            "behaviour_delta": 0.0,
            "behaviour_reasons": [],
        }

    base_risk_score = 0.0
    if label and score_prob is not None:
        reasons = predictive_model.explain_reasons(vec, label)
        # Add simple contextual reason from extras
        days_left = extras.get("days_left")
        if days_left is not None:
            if days_left <= 60:
                reasons.append("Warranty is close to expiry.")
            else:
                reasons.append("Warranty still has time left.")
        if extras.get("maintenance_count", 0) == 0:
            reasons.append("No maintenance recorded.")
        risk_label = label
        risk_score = float(score_prob)
        base_risk_score = risk_score
    else:
        # fallback heuristic
        risk_score, fallback_reasons = derive_score(store.get_telemetry(user_id, warranty_id))
        risk_label = "HIGH" if risk_score > 0.66 else "MEDIUM" if risk_score >= 0.33 else "LOW"
        reasons = fallback_reasons or ["Predictive engine not ready yet."]
        base_risk_score = risk_score

    behaviour_signal = compute_behaviour_risk_signal(user_id, warranty_id)
    behaviour_delta = float(behaviour_signal.get("behaviour_risk_delta", 0.0))
    behaviour_reasons = behaviour_signal.get("reasons", [])
    if behaviour_delta:
        adjusted_score = max(0.0, min(1.0, base_risk_score + behaviour_delta))
        risk_score = adjusted_score
        reasons = behaviour_reasons + reasons
    # Final label based on adjusted score
    risk_label = "HIGH" if risk_score > 0.66 else "MEDIUM" if risk_score >= 0.33 else "LOW"

    logger.info(
        "predictive_behaviour_adjust",
        extra={
            "user_id": user_id,
            "warranty_id": warranty_id,
            "base_score": round(float(base_risk_score), 3),
            "behaviour_delta": behaviour_delta,
            "final_score": round(float(risk_score), 3),
            "final_label": risk_label,
        },
    )

    return {
        "risk_label": risk_label,
        "risk_score": round(float(risk_score), 3),
        "proba": proba_map,
        "reasons": reasons[:4] if reasons else ["Predictive engine not ready yet."],
        "base_risk_score": round(float(base_risk_score), 3),
        "behaviour_delta": round(float(behaviour_delta), 3),
        "behaviour_reasons": behaviour_reasons[:4] if behaviour_reasons else [],
    }


def compute_predictive_score(user_id: str, warranty_id: str, model_code: str | None, region: str | None, timezone: str | None) -> PredictiveScore:
    """Backward-compatible object for internal use."""
    result = score_warranty(user_id, warranty_id)
    band = result.get("risk_label", "LOW").lower()
    questions = suggest_questions(store.get_telemetry(user_id, warranty_id))
    return PredictiveScore(
        warranty_id=warranty_id,
        user_id=user_id,
        model_code=model_code,
        region=region,
        score=float(result.get("risk_score", 0.0)),
        band=band,
        reasons=result.get("reasons", []),
        suggested_questions=questions,
    )


def health() -> Tuple[bool, str]:
    predictive_model.load()
    if predictive_model.error:
        return False, f"Model error: {predictive_model.error}"
    if not predictive_model.model:
        return False, "Model not loaded"
    return True, "Model loaded"


def score_warranty_from_db(db, user_id: str, warranty_id: str):
    # Thin wrapper to match helper signature; reuses score_warranty.
    return score_warranty(user_id, warranty_id)
