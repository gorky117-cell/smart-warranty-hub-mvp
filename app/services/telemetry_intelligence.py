import os
from collections import Counter
from datetime import datetime, timedelta
from typing import Any, Dict, Iterable, Optional

from ..db_models import TelemetryEventDB, WarrantyDB


_SENSITIVE_KEYS = {
    "name",
    "email",
    "phone",
    "address",
    "serial",
    "serial_no",
    "imei",
    "invoice_no",
    "lat",
    "latitude",
    "lon",
    "lng",
    "longitude",
    "location",
    "gps",
}
_MAX_TEXT_VALUE = int(os.getenv("TELEMETRY_MAX_TEXT_VALUE", "120"))
_MIN_OEM_COHORT = int(os.getenv("OEM_TELEMETRY_MIN_COHORT", "10"))


def _to_float(value: Any) -> Optional[float]:
    try:
        if value is None or value == "":
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _safe_value(value: Any) -> Any:
    if isinstance(value, str):
        return value[:_MAX_TEXT_VALUE]
    if isinstance(value, (int, float, bool)) or value is None:
        return value
    if isinstance(value, list):
        return [_safe_value(v) for v in value[:20]]
    if isinstance(value, dict):
        return sanitize_payload(value)
    return str(value)[:_MAX_TEXT_VALUE]


def sanitize_payload(payload: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Remove direct identifiers and bound payload values before persistence/RAG."""
    clean: Dict[str, Any] = {}
    for key, value in (payload or {}).items():
        safe_key = str(key).strip()[:64]
        if not safe_key:
            continue
        if safe_key.lower() in _SENSITIVE_KEYS:
            continue
        clean[safe_key] = _safe_value(value)
    return clean


def classify_event(event_type: str, payload: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    payload = payload or {}
    event = (event_type or "").strip().lower()
    hours = _to_float(payload.get("hours"))
    errors = _to_float(payload.get("errors"))
    temp = _to_float(payload.get("temperature") or payload.get("temp_c") or payload.get("max_temp_seen"))
    voltage = _to_float(payload.get("voltage"))

    reasons = []
    risk_points = 0
    care_points = 0

    if event in {"failure", "error", "overheating", "shutdown"}:
        risk_points += 2 if event == "failure" else 1
        reasons.append(f"{event} event reported")
    if errors and errors > 0:
        risk_points += 1 if errors <= 3 else 2
        reasons.append("device errors reported")
    if hours and hours >= 1000:
        risk_points += 1
        reasons.append("high cumulative usage")
    if temp and temp >= 45:
        risk_points += 1
        reasons.append("high operating temperature")
    if voltage and (voltage < 190 or voltage > 250):
        risk_points += 1
        reasons.append("voltage outside normal range")
    if event in {"maintenance", "service", "cleaning"}:
        care_points += 1
        reasons.append("care or maintenance activity reported")

    if risk_points >= 3:
        signal = "high_risk"
    elif risk_points:
        signal = "watch"
    elif care_points:
        signal = "care_positive"
    else:
        signal = "neutral"

    return {
        "signal": signal,
        "risk_points": risk_points,
        "care_points": care_points,
        "reasons": reasons[:4],
    }


def prepare_event_payload(event_type: str, payload: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    clean = sanitize_payload(payload)
    clean["_telemetry_intelligence"] = classify_event(event_type, clean)
    return clean


def build_oem_telemetry_aggregate(
    db,
    *,
    brand: Optional[str] = None,
    model: Optional[str] = None,
    product_type: Optional[str] = None,
    region: Optional[str] = None,
    min_cohort: Optional[int] = None,
    days: int = 90,
) -> Dict[str, Any]:
    threshold = _MIN_OEM_COHORT if min_cohort is None else max(1, int(min_cohort))
    cutoff = datetime.utcnow() - timedelta(days=max(1, int(days)))
    rows: Iterable[TelemetryEventDB] = (
        db.query(TelemetryEventDB).filter(TelemetryEventDB.timestamp >= cutoff).all()
    )

    warranties = {w.id: w for w in db.query(WarrantyDB).all()}
    users = set()
    events = 0
    signals: Counter = Counter()
    event_types: Counter = Counter()
    risk_points = 0
    care_points = 0

    for row in rows:
        warranty = warranties.get(row.warranty_id)
        if (brand or model or product_type or region) and not warranty:
            continue
        if brand and warranty and (warranty.brand or "").lower() != brand.lower():
            continue
        if model and warranty and (warranty.model_code or "").lower() != model.lower():
            continue
        if region and warranty and ((warranty.region_code or row.region or "").lower() != region.lower()):
            continue
        if product_type and warranty and product_type.lower() not in (warranty.product_name or "").lower():
            continue

        intel = ((row.payload or {}).get("_telemetry_intelligence") or {})
        signal = intel.get("signal") or "unknown"
        signals[signal] += 1
        event_types[row.event_type or "unknown"] += 1
        risk_points += int(intel.get("risk_points") or 0)
        care_points += int(intel.get("care_points") or 0)
        users.add(row.user_id)
        events += 1

    if len(users) < threshold:
        return {
            "status": "suppressed",
            "reason": "minimum cohort threshold not met",
            "min_cohort": threshold,
            "cohort_size": len(users),
        }

    return {
        "status": "ok",
        "min_cohort": threshold,
        "cohort_size": len(users),
        "event_count": events,
        "signals": dict(signals),
        "event_types": dict(event_types),
        "risk_points": risk_points,
        "care_points": care_points,
        "window_days": days,
    }
