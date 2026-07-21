from __future__ import annotations

import json
import os
import logging
from typing import List, Dict, Optional, Tuple

logger = logging.getLogger(__name__)

DATA_PATH = os.path.join("data", "behaviour_answers.jsonl")


QUESTION_BANK: List[Dict] = [
    {"id": "q0_serial", "text": "Can you add the product serial number?", "answer_type": "text", "options": [], "tags": ["serial"]},
    {"id": "q0_region", "text": "Which country or region is this product used in?", "answer_type": "text", "options": [], "tags": ["region"]},
    {"id": "q1_usage_location", "text": "Where is the product used most?", "answer_type": "choice", "options": ["Home", "Office", "Outdoor", "Mixed"], "tags": ["environment"]},
    {"id": "q2_daily_usage", "text": "Average daily usage?", "answer_type": "choice", "options": ["Low", "Medium", "High"], "tags": ["usage"]},
    {"id": "q3_voltage", "text": "Do you notice voltage fluctuations?", "answer_type": "choice", "options": ["Yes", "No", "Not sure"], "tags": ["power"]},
    {"id": "q4_install", "text": "Installed by authorized technician?", "answer_type": "choice", "options": ["Yes", "No", "Not sure"], "tags": ["care"]},
    {"id": "q5_environment", "text": "Environment?", "answer_type": "choice", "options": ["Humid", "Dusty", "Normal"], "tags": ["environment"]},
    {"id": "q6_overheat", "text": "Ever overheated or shut down unexpectedly?", "answer_type": "choice", "options": ["Yes", "No"], "tags": ["issues"]},
]


def _question_by_id(question_id: str) -> Optional[Dict]:
    for q in QUESTION_BANK:
        if q.get("id") == question_id:
            return q
    return None


def _answered_tag(answered_questions: set, tag: str) -> bool:
    for q in QUESTION_BANK:
        if q.get("id") in answered_questions and tag in (q.get("tags") or []):
            return True
    return False


def _payload_value(payload: Dict, *keys: str):
    for key in keys:
        if key in payload and payload.get(key) not in (None, ""):
            return payload.get(key)
    return None


def _telemetry_signals(events: Optional[List[object]]) -> Dict[str, bool]:
    signals = {
        "voltage_issue": False,
        "high_usage": False,
        "overheat_shutdown": False,
        "usage_seen": False,
    }
    for ev in events or []:
        event_type = str(getattr(ev, "event_type", "") or "").lower()
        payload = getattr(ev, "payload", None) or {}
        if event_type == "usage":
            signals["usage_seen"] = True
        if event_type in {"overheating", "shutdown"}:
            signals["overheat_shutdown"] = True
        intel = payload.get("_telemetry_intelligence") or {}
        reasons = " ".join(str(r).lower() for r in (intel.get("reasons") or []))
        if "voltage" in reasons:
            signals["voltage_issue"] = True
        if "temperature" in reasons or "overheat" in reasons or "shutdown" in reasons:
            signals["overheat_shutdown"] = True
        voltage = _payload_value(payload, "voltage")
        if voltage is not None:
            try:
                v = float(voltage)
                if v < 190 or v > 250:
                    signals["voltage_issue"] = True
            except (TypeError, ValueError):
                pass
        hours = _payload_value(payload, "hours", "usage_hours")
        if hours is not None:
            signals["usage_seen"] = True
            try:
                if float(hours) >= 1000:
                    signals["high_usage"] = True
            except (TypeError, ValueError):
                pass
        errors = _payload_value(payload, "errors")
        if errors is not None:
            try:
                if float(errors) >= 5 and ("temp" in str(payload).lower() or "heat" in str(payload).lower()):
                    signals["overheat_shutdown"] = True
            except (TypeError, ValueError):
                pass
    return signals


def _ensure_data_path():
    os.makedirs(os.path.dirname(DATA_PATH), exist_ok=True)


def _load_answers(user_id: str, warranty_id: str) -> List[Dict]:
    """Load all answers for a user+warranty from JSONL (fallback when Mongo not used)."""
    if not os.path.exists(DATA_PATH):
        return []
    results: List[Dict] = []
    try:
        with open(DATA_PATH, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    rec = json.loads(line)
                except Exception:
                    continue
                if rec.get("user_id") == user_id and rec.get("warranty_id") == warranty_id:
                    results.append(rec)
    except Exception as e:
        logger.exception("Failed to read behaviour answers file", exc_info=e)
    return results


def _append_answer(rec: Dict):
    _ensure_data_path()
    try:
        with open(DATA_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec) + "\n")
    except Exception as e:
        logger.exception("Failed to append behaviour answer", exc_info=e)


def get_next_question(user_id: str, warranty_id: str) -> Tuple[Optional[Dict], bool]:
    """
    Return next unanswered question and done flag.
    """
    answered = {a.get("question_id") for a in _load_answers(user_id, warranty_id)}
    for q in QUESTION_BANK:
        if q["id"] not in answered:
            return q, False
    return None, True


def get_next_useful_question(
    user_id: str,
    warranty_id: str,
    *,
    warranty: object | None = None,
    telemetry_events: Optional[List[object]] = None,
) -> Tuple[Optional[Dict], bool, str]:
    """
    Return at most one question when a missing field or signal makes it useful.
    """
    answered = {a.get("question_id") for a in _load_answers(user_id, warranty_id)}
    serial = getattr(warranty, "serial_no", None) if warranty is not None else None
    region = getattr(warranty, "region_code", None) if warranty is not None else None
    signals = _telemetry_signals(telemetry_events)

    candidates: List[Tuple[str, str]] = []
    if not serial:
        candidates.append(("q0_serial", "serial_missing"))
    if not region:
        candidates.append(("q0_region", "country_region_unknown"))
    if signals["voltage_issue"]:
        candidates.append(("q3_voltage", "voltage_issue_reported"))
    if signals["high_usage"] or (not signals["usage_seen"] and not _answered_tag(answered, "usage")):
        candidates.append(("q2_daily_usage", "usage_context_needed"))
    if signals["overheat_shutdown"]:
        candidates.append(("q6_overheat", "overheating_shutdown_signal"))
    if not _answered_tag(answered, "environment"):
        candidates.append(("q1_usage_location", "environment_context_needed"))

    for question_id, reason in candidates:
        if question_id in answered:
            continue
        q = _question_by_id(question_id)
        if q:
            out = dict(q)
            out["reason"] = reason
            return out, False, reason
    return None, True, "no_useful_question"


def record_answer(user_id: str, warranty_id: str, question_id: str, answer: str) -> bool:
    rec = {
        "user_id": user_id,
        "warranty_id": warranty_id,
        "question_id": question_id,
        "answer": answer,
    }
    _append_answer(rec)
    return True
