from __future__ import annotations

import json
import os
import logging
from typing import List, Dict, Optional, Tuple

from .product_recommendations import infer_product_category

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


PRODUCT_QUESTION_BANK: Dict[str, List[Dict]] = {
    "printer": [
        {"id": "pq_printer_dry_ink", "text": "Has the ink tank or cartridge ever run dry?", "answer_type": "choice", "options": ["Yes", "No", "Not sure"], "tags": ["product_behaviour", "printer", "ink"]},
        {"id": "pq_printer_nozzle", "text": "Have you seen nozzle check failures or missing lines recently?", "answer_type": "choice", "options": ["Yes", "No", "Not sure"], "tags": ["product_behaviour", "printer", "print_quality"]},
        {"id": "pq_printer_cleaning", "text": "Have you run printhead cleaning recently?", "answer_type": "choice", "options": ["Yes", "No", "Not sure"], "tags": ["product_behaviour", "printer", "maintenance"]},
    ],
    "smartphone": [
        {"id": "pq_phone_overheat", "text": "Does the phone overheat or shut down during normal use?", "answer_type": "choice", "options": ["Yes", "No", "Not sure"], "tags": ["product_behaviour", "phone", "overheat"]},
        {"id": "pq_phone_charge", "text": "Do you use the original or a properly rated charger?", "answer_type": "choice", "options": ["Yes", "No", "Not sure"], "tags": ["product_behaviour", "phone", "power"]},
    ],
    "laptop": [
        {"id": "pq_laptop_heat", "text": "Does the laptop get unusually hot or shut down under load?", "answer_type": "choice", "options": ["Yes", "No", "Not sure"], "tags": ["product_behaviour", "laptop", "overheat"]},
        {"id": "pq_laptop_backup", "text": "Are important files backed up outside this laptop?", "answer_type": "choice", "options": ["Yes", "No", "Not sure"], "tags": ["product_behaviour", "laptop", "data"]},
    ],
    "fridge": [
        {"id": "pq_fridge_temp", "text": "Have you noticed unstable cooling or temperature changes?", "answer_type": "choice", "options": ["Yes", "No", "Not sure"], "tags": ["product_behaviour", "fridge", "cooling"]},
        {"id": "pq_fridge_gasket", "text": "Does the door seal look loose, cracked, or unable to close tightly?", "answer_type": "choice", "options": ["Yes", "No", "Not sure"], "tags": ["product_behaviour", "fridge", "seal"]},
    ],
    "tv": [
        {"id": "pq_tv_surge", "text": "Is the TV connected through surge protection or stable power?", "answer_type": "choice", "options": ["Yes", "No", "Not sure"], "tags": ["product_behaviour", "tv", "power"]},
        {"id": "pq_tv_panel", "text": "Have you noticed panel lines, flicker, or dark spots?", "answer_type": "choice", "options": ["Yes", "No", "Not sure"], "tags": ["product_behaviour", "tv", "display"]},
    ],
    "heater": [
        {"id": "pq_heater_trip", "text": "Has the heater tripped power or smelled hot during use?", "answer_type": "choice", "options": ["Yes", "No", "Not sure"], "tags": ["product_behaviour", "heater", "power"]},
        {"id": "pq_heater_clearance", "text": "Is there clear space around the heater while it runs?", "answer_type": "choice", "options": ["Yes", "No", "Not sure"], "tags": ["product_behaviour", "heater", "environment"]},
    ],
    "water_heater": [
        {"id": "pq_geyser_leak", "text": "Have you noticed leakage, tripping, or unusual heating from the geyser?", "answer_type": "choice", "options": ["Yes", "No", "Not sure"], "tags": ["product_behaviour", "water_heater", "safety"]},
        {"id": "pq_geyser_scale", "text": "Is the product used in a hard-water area?", "answer_type": "choice", "options": ["Yes", "No", "Not sure"], "tags": ["product_behaviour", "water_heater", "water_quality"]},
    ],
    "fan": [
        {"id": "pq_fan_wobble", "text": "Does the fan wobble, vibrate, or make unusual noise?", "answer_type": "choice", "options": ["Yes", "No", "Not sure"], "tags": ["product_behaviour", "fan", "noise"]},
    ],
    "air_conditioner": [
        {"id": "pq_ac_filter", "text": "When were the AC filters last cleaned?", "answer_type": "choice", "options": ["This month", "Over 3 months ago", "Not sure"], "tags": ["product_behaviour", "air_conditioner", "maintenance"]},
        {"id": "pq_ac_cooling", "text": "Has cooling dropped or water leakage appeared recently?", "answer_type": "choice", "options": ["Yes", "No", "Not sure"], "tags": ["product_behaviour", "air_conditioner", "cooling"]},
    ],
    "washing_machine": [
        {"id": "pq_washer_vibration", "text": "Does the washing machine vibrate heavily or move during spin?", "answer_type": "choice", "options": ["Yes", "No", "Not sure"], "tags": ["product_behaviour", "washing_machine", "vibration"]},
        {"id": "pq_washer_drain", "text": "Have you noticed slow draining or repeated filter blockage?", "answer_type": "choice", "options": ["Yes", "No", "Not sure"], "tags": ["product_behaviour", "washing_machine", "drain"]},
    ],
    "microwave": [
        {"id": "pq_microwave_heat", "text": "Has heating become uneven or slower than before?", "answer_type": "choice", "options": ["Yes", "No", "Not sure"], "tags": ["product_behaviour", "microwave", "heating"]},
    ],
    "camera": [
        {"id": "pq_camera_moisture", "text": "Has the camera been exposed to moisture, dust, or impact?", "answer_type": "choice", "options": ["Yes", "No", "Not sure"], "tags": ["product_behaviour", "camera", "environment"]},
    ],
    "router": [
        {"id": "pq_router_drop", "text": "Does the router disconnect or restart frequently?", "answer_type": "choice", "options": ["Yes", "No", "Not sure"], "tags": ["product_behaviour", "router", "stability"]},
    ],
    "wearable": [
        {"id": "pq_wearable_charge", "text": "Does the wearable fail to charge or track reliably?", "answer_type": "choice", "options": ["Yes", "No", "Not sure"], "tags": ["product_behaviour", "wearable", "charging"]},
    ],
    "audio": [
        {"id": "pq_audio_distortion", "text": "Have you noticed distortion, crackling, or charging problems?", "answer_type": "choice", "options": ["Yes", "No", "Not sure"], "tags": ["product_behaviour", "audio", "sound"]},
    ],
    "purifier": [
        {"id": "pq_purifier_filter", "text": "When was the filter or cartridge last cleaned or replaced?", "answer_type": "choice", "options": ["Recently", "Overdue", "Not sure"], "tags": ["product_behaviour", "purifier", "filter"]},
    ],
    "kitchen_appliance": [
        {"id": "pq_kitchen_motor", "text": "Does the motor smell hot, slow down, or stop during heavy use?", "answer_type": "choice", "options": ["Yes", "No", "Not sure"], "tags": ["product_behaviour", "kitchen_appliance", "motor"]},
    ],
    "cooler": [
        {"id": "pq_cooler_flow", "text": "Is water flow weak or are the cooling pads dirty?", "answer_type": "choice", "options": ["Yes", "No", "Not sure"], "tags": ["product_behaviour", "cooler", "water_flow"]},
    ],
    "inverter": [
        {"id": "pq_inverter_backup", "text": "Has backup time dropped or load exceeded the inverter rating?", "answer_type": "choice", "options": ["Yes", "No", "Not sure"], "tags": ["product_behaviour", "inverter", "battery"]},
    ],
    "appliance": [
        {"id": "pq_appliance_install", "text": "Was the product installed according to OEM guidance?", "answer_type": "choice", "options": ["Yes", "No", "Not sure"], "tags": ["product_behaviour", "appliance", "installation"]},
    ],
}


def _question_by_id(question_id: str) -> Optional[Dict]:
    for q in QUESTION_BANK + [item for items in PRODUCT_QUESTION_BANK.values() for item in items]:
        if q.get("id") == question_id:
            return q
    return None


def _answered_tag(answered_questions: set, tag: str) -> bool:
    for q in QUESTION_BANK + [item for items in PRODUCT_QUESTION_BANK.values() for item in items]:
        if q.get("id") in answered_questions and tag in (q.get("tags") or []):
            return True
    return False


def _warranty_context(warranty: object | None) -> Dict:
    if warranty is None:
        return {}
    return {
        "product_type": getattr(warranty, "product_type", None),
        "product_name": getattr(warranty, "product_name", None),
        "model_code": getattr(warranty, "model_code", None),
        "brand": getattr(warranty, "brand", None),
    }


def _product_question_candidates(warranty: object | None) -> List[Tuple[str, str]]:
    category = infer_product_category(_warranty_context(warranty))
    return [(q["id"], f"{category}_behaviour_context_needed") for q in PRODUCT_QUESTION_BANK.get(category, [])]


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
    if signals["voltage_issue"]:
        candidates.append(("q3_voltage", "voltage_issue_reported"))
    if signals["overheat_shutdown"]:
        candidates.append(("q6_overheat", "overheating_shutdown_signal"))
    candidates.extend(_product_question_candidates(warranty))
    if not region:
        candidates.append(("q0_region", "country_region_unknown"))
    if signals["high_usage"] or (not signals["usage_seen"] and not _answered_tag(answered, "usage")):
        candidates.append(("q2_daily_usage", "usage_context_needed"))
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
