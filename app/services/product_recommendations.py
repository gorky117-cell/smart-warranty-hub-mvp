from __future__ import annotations

import datetime as dt
import json
import os
from typing import List, Optional, TypedDict, Literal, Dict

try:
    from pymongo import MongoClient  # type: ignore
except Exception:  # pymongo may not be installed
    MongoClient = None  # type: ignore


class ProductRecommendation(TypedDict, total=False):
    product_id: str
    title: str
    category: str
    region: Optional[str]
    risk_band: str
    why: str
    priority: int
    cta_label: str
    cta_url: Optional[str]
    # Optional fields kept for backward compatibility with existing UI renderers
    action: str
    description: str
    reason: str


PRODUCT_CATALOG: List[Dict] = [
    # Smartphones
    {"product_id": "sp_ultra", "category": "smartphone", "title": "Ultra smartphone upgrade", "supported_regions": ["APAC", "EU", "NA"], "min_risk_band": "HIGH", "priority": 1, "tags": ["upgrade", "premium"]},
    {"product_id": "sp_case_bundle", "category": "smartphone", "title": "Rugged case + protector", "supported_regions": ["APAC", "EU", "NA"], "min_risk_band": "LOW", "priority": 2, "tags": ["accessory", "protection"]},
    {"product_id": "sp_extended", "category": "smartphone", "title": "Phone extended warranty", "supported_regions": ["APAC", "EU", "NA"], "min_risk_band": "MEDIUM", "priority": 3, "tags": ["warranty"]},
    # Laptops
    {"product_id": "lt_protect", "category": "laptop", "title": "Accidental damage protection", "supported_regions": ["APAC", "EU", "NA"], "min_risk_band": "MEDIUM", "priority": 2, "tags": ["warranty"]},
    {"product_id": "lt_backup", "category": "laptop", "title": "Cloud backup bundle", "supported_regions": None, "min_risk_band": "HIGH", "priority": 3, "tags": ["backup"]},
    {"product_id": "lt_cooling", "category": "laptop", "title": "Cooling pad + cleaner", "supported_regions": None, "min_risk_band": "LOW", "priority": 4, "tags": ["care"]},
    # Appliances / EV
    {"product_id": "ap_surge", "category": "appliance", "title": "Surge protector + stabilizer", "supported_regions": None, "min_risk_band": "LOW", "priority": 2, "tags": ["protection"]},
    {"product_id": "ap_service", "category": "appliance", "title": "Preventive service visit", "supported_regions": ["APAC"], "min_risk_band": "MEDIUM", "priority": 3, "tags": ["care"]},
    {"product_id": "ev_warranty", "category": "ev", "title": "EV battery cover", "supported_regions": None, "min_risk_band": "MEDIUM", "priority": 2, "tags": ["ev"]},
    {"product_id": "ev_charger", "category": "ev", "title": "Smart home charger", "supported_regions": ["EU", "NA"], "min_risk_band": "LOW", "priority": 4, "tags": ["ev"]},
    # General
    {"product_id": "gn_backup", "category": "general", "title": "Data backup & sync", "supported_regions": None, "min_risk_band": "HIGH", "priority": 4, "tags": ["backup"]},
    {"product_id": "gn_inspect", "category": "general", "title": "Annual inspection coupon", "supported_regions": None, "min_risk_band": "MEDIUM", "priority": 5, "tags": ["maintenance"]},
    {"product_id": "gn_cleaning", "category": "general", "title": "Cleaning kit", "supported_regions": None, "min_risk_band": "LOW", "priority": 6, "tags": ["care"]},
]


CARE_CATALOG: Dict[str, List[Dict]] = {
    "printer": [
        {"product_id": "printer_ink_level", "title": "Keep ink tanks from running dry", "why": "General care advice for ink tank printers. This is not a warranty coverage promise.", "priority": 1},
        {"product_id": "printer_nozzle_check", "title": "Run a nozzle check when print quality drops", "why": "General care advice based on the product type. Clean only when needed to avoid unnecessary ink use.", "priority": 2},
        {"product_id": "printer_periodic_print", "title": "Print periodically if the printer sits idle", "why": "General preventive care for inkjet printheads. This does not change OEM warranty terms.", "priority": 3},
        {"product_id": "printer_genuine_ink", "title": "Use compatible or OEM-recommended ink", "why": "General care advice to reduce clogging and print-quality issues.", "priority": 4},
    ],
    "smartphone": [
        {"product_id": "phone_battery_care", "title": "Protect battery health", "why": "General care advice: avoid heat and repeated deep discharge where practical.", "priority": 1},
        {"product_id": "phone_screen_case", "title": "Use screen and case protection", "why": "General preventive care for accidental damage risk. This is not a warranty coverage promise.", "priority": 2},
        {"product_id": "phone_charger", "title": "Use a reliable charger and cable", "why": "General care advice to reduce charging and port issues.", "priority": 3},
    ],
    "laptop": [
        {"product_id": "laptop_backup", "title": "Keep backups current", "why": "General care advice for devices that store user data.", "priority": 1},
        {"product_id": "laptop_cooling", "title": "Keep vents clear and manage heat", "why": "General preventive care for laptops under daily use.", "priority": 2},
        {"product_id": "laptop_charger", "title": "Use the correct charger rating", "why": "General care advice to avoid power and battery issues.", "priority": 3},
    ],
    "fridge": [
        {"product_id": "fridge_gasket", "title": "Check the door gasket seal", "why": "General preventive care for cooling efficiency.", "priority": 1},
        {"product_id": "fridge_coils", "title": "Keep coils and vents clear", "why": "General care advice to reduce compressor strain.", "priority": 2},
        {"product_id": "fridge_temperature", "title": "Keep temperature settings stable", "why": "General care advice for consistent cooling.", "priority": 3},
    ],
    "tv": [
        {"product_id": "tv_surge", "title": "Use surge protection", "why": "General care advice for electronics exposed to voltage fluctuation.", "priority": 1},
        {"product_id": "tv_panel_care", "title": "Clean the panel gently", "why": "General care advice to avoid screen or coating damage.", "priority": 2},
        {"product_id": "tv_ventilation", "title": "Keep ventilation space around the TV", "why": "General preventive care for heat management.", "priority": 3},
    ],
    "appliance": [
        {"product_id": "appliance_voltage", "title": "Use stable power where required", "why": "General care advice for appliances sensitive to voltage fluctuation.", "priority": 1},
        {"product_id": "appliance_installation", "title": "Follow installation guidance", "why": "General preventive care; installation mistakes can cause avoidable issues.", "priority": 2},
        {"product_id": "appliance_service", "title": "Schedule preventive service when symptoms appear", "why": "General care advice for early issue handling.", "priority": 3},
    ],
    "heater": [
        {"product_id": "heater_clearance", "title": "Keep safe clearance around the heater", "why": "General care advice for heaters. This is not a warranty coverage promise.", "priority": 1},
        {"product_id": "heater_power", "title": "Use a properly rated socket", "why": "General care advice to reduce overheating and power issues.", "priority": 2},
        {"product_id": "heater_dust", "title": "Keep vents and grills dust-free", "why": "General preventive care for airflow and heat transfer.", "priority": 3},
    ],
    "water_heater": [
        {"product_id": "water_heater_pressure", "title": "Check pressure valve and installation safety", "why": "General care advice for geysers and water heaters. Follow OEM installation guidance.", "priority": 1},
        {"product_id": "water_heater_scale", "title": "Watch for scale buildup in hard-water areas", "why": "General preventive care; warranty coverage still depends on official terms.", "priority": 2},
        {"product_id": "water_heater_leak", "title": "Act early on leaks or tripping", "why": "General care advice to avoid larger service issues.", "priority": 3},
    ],
    "fan": [
        {"product_id": "fan_balance", "title": "Keep blades balanced and clean", "why": "General care advice to reduce vibration and motor strain.", "priority": 1},
        {"product_id": "fan_mounting", "title": "Check mounting if wobble appears", "why": "General preventive care for safe operation.", "priority": 2},
        {"product_id": "fan_speed_noise", "title": "Log unusual speed or noise changes", "why": "General care advice for early fault detection.", "priority": 3},
    ],
    "air_conditioner": [
        {"product_id": "ac_filter", "title": "Clean filters on schedule", "why": "General care advice for cooling efficiency and airflow.", "priority": 1},
        {"product_id": "ac_drain", "title": "Watch for drain blockage or water leakage", "why": "General preventive care for AC units.", "priority": 2},
        {"product_id": "ac_voltage", "title": "Use stable power where required", "why": "General care advice; compressor warranty depends on official OEM terms.", "priority": 3},
    ],
    "washing_machine": [
        {"product_id": "washer_load", "title": "Avoid overloading the drum", "why": "General care advice to reduce motor and bearing strain.", "priority": 1},
        {"product_id": "washer_filter", "title": "Clean lint/filter areas regularly", "why": "General preventive care for drainage and wash quality.", "priority": 2},
        {"product_id": "washer_level", "title": "Keep the machine level", "why": "General care advice to reduce vibration and noise.", "priority": 3},
    ],
    "microwave": [
        {"product_id": "microwave_container", "title": "Use microwave-safe containers", "why": "General care advice for safe operation.", "priority": 1},
        {"product_id": "microwave_clean", "title": "Keep the cavity and door seal clean", "why": "General preventive care for heating consistency.", "priority": 2},
        {"product_id": "microwave_metal", "title": "Avoid metal inside the microwave", "why": "General care advice; misuse may affect service eligibility.", "priority": 3},
    ],
    "camera": [
        {"product_id": "camera_lens", "title": "Protect lens and sensor areas", "why": "General care advice for cameras and lenses.", "priority": 1},
        {"product_id": "camera_moisture", "title": "Avoid moisture and dust exposure", "why": "General preventive care; liquid/dust coverage depends on official terms.", "priority": 2},
        {"product_id": "camera_battery", "title": "Store batteries safely when idle", "why": "General care advice for battery health.", "priority": 3},
    ],
    "router": [
        {"product_id": "router_ventilation", "title": "Keep the router ventilated", "why": "General care advice to reduce heat-related instability.", "priority": 1},
        {"product_id": "router_power", "title": "Use the correct adapter", "why": "General preventive care for network hardware.", "priority": 2},
        {"product_id": "router_firmware", "title": "Keep firmware updated when available", "why": "General care advice for stability and security.", "priority": 3},
    ],
    "wearable": [
        {"product_id": "wearable_charge", "title": "Charge with the correct dock or cable", "why": "General care advice for wearables and smartwatches.", "priority": 1},
        {"product_id": "wearable_clean", "title": "Keep sensors and strap contacts clean", "why": "General preventive care for reliable readings and charging.", "priority": 2},
        {"product_id": "wearable_water", "title": "Respect water-resistance limits", "why": "General care advice; water damage coverage depends on official terms.", "priority": 3},
    ],
    "audio": [
        {"product_id": "audio_volume", "title": "Avoid sustained maximum volume", "why": "General care advice to reduce speaker strain.", "priority": 1},
        {"product_id": "audio_charge", "title": "Use the correct charger for powered speakers", "why": "General preventive care for battery and power issues.", "priority": 2},
        {"product_id": "audio_moisture", "title": "Keep ports and grills dry", "why": "General care advice; water resistance depends on official terms.", "priority": 3},
    ],
    "purifier": [
        {"product_id": "purifier_filter", "title": "Replace or clean filters on schedule", "why": "General care advice for air or water purifiers.", "priority": 1},
        {"product_id": "purifier_flow", "title": "Watch for weak flow or unusual noise", "why": "General preventive care for early service signals.", "priority": 2},
        {"product_id": "purifier_installation", "title": "Follow installation and cartridge guidance", "why": "General care advice; coverage depends on official OEM terms.", "priority": 3},
    ],
    "kitchen_appliance": [
        {"product_id": "kitchen_overload", "title": "Avoid overloading the motor", "why": "General care advice for mixers, blenders and food processors.", "priority": 1},
        {"product_id": "kitchen_clean_dry", "title": "Clean and dry jars, blades and seals after use", "why": "General preventive care for hygiene and component life.", "priority": 2},
        {"product_id": "kitchen_cooldown", "title": "Let the motor cool after heavy use", "why": "General care advice to reduce overheating.", "priority": 3},
    ],
    "cooler": [
        {"product_id": "cooler_water", "title": "Use clean water and drain stale water", "why": "General care advice for air coolers.", "priority": 1},
        {"product_id": "cooler_pads", "title": "Clean cooling pads and tank regularly", "why": "General preventive care for airflow and odor control.", "priority": 2},
        {"product_id": "cooler_pump", "title": "Watch pump noise or weak water flow", "why": "General care advice for early service signals.", "priority": 3},
    ],
    "inverter": [
        {"product_id": "inverter_ventilation", "title": "Keep inverter and battery area ventilated", "why": "General care advice for inverter systems.", "priority": 1},
        {"product_id": "inverter_load", "title": "Avoid exceeding rated load", "why": "General preventive care for power electronics.", "priority": 2},
        {"product_id": "inverter_battery", "title": "Check battery terminals and backup changes", "why": "General care advice; battery warranty depends on official terms.", "priority": 3},
    ],
    "general": [
        {"product_id": "general_manual", "title": "Keep invoice, serial number, and manual available", "why": "General care advice for faster support. Warranty coverage still depends on official terms.", "priority": 1},
        {"product_id": "general_clean", "title": "Keep the product clean and dry", "why": "General preventive care for products without a specific care profile.", "priority": 2},
        {"product_id": "general_usage_notes", "title": "Log unusual errors or service events", "why": "General care advice to make future support easier.", "priority": 3},
    ],
}


_RISK_ORDER = {"LOW": 0, "MEDIUM": 1, "HIGH": 2}


def _risk_band(label: Optional[str], score: Optional[float]) -> str:
    if label and label.upper() in _RISK_ORDER:
        return label.upper()
    try:
        if score is None:
            raise ValueError
        if score < 0.33:
            return "LOW"
        if score < 0.66:
            return "MEDIUM"
        return "HIGH"
    except Exception:
        return "MEDIUM"


def infer_product_category(warranty: Dict) -> str:
    pt = str(warranty.get("product_type") or "").lower()
    name = (warranty.get("product_name") or "").lower()
    model = (warranty.get("model_code") or "").lower()
    joined = " ".join([pt, name, model])
    if any(k in joined for k in ["printer", "inkjet", "ecotank", "laserjet"]):
        return "printer"
    if any(k in joined for k in ["geyser", "water heater", "instant heater"]):
        return "water_heater"
    if any(k in joined for k in ["oil heater", "room heater", "space heater", "radiator heater", "heater"]):
        return "heater"
    if any(k in joined for k in ["ceiling fan", "table fan", "pedestal fan", "exhaust fan", "fan"]):
        return "fan"
    if any(k in joined for k in ["air cooler", "desert cooler", "cooler"]):
        return "cooler"
    if any(k in joined for k in ["inverter", "ups", "home ups"]):
        return "inverter"
    if "phone" in name or "phone" in pt or "galaxy" in name or "iphone" in name or "sm-" in model:
        return "smartphone"
    if "laptop" in name or "notebook" in name or "laptop" in pt:
        return "laptop"
    if "ev" in name or "ev" in pt or "battery" in name:
        return "ev"
    if any(k in joined for k in ["fridge", "refrigerator"]):
        return "fridge"
    if any(k in joined for k in ["tv", "television", "oled", "led tv", "smart tv"]):
        return "tv"
    if any(k in joined for k in ["air conditioner", "airconditioner", "split ac", "window ac", "portable ac"]):
        return "air_conditioner"
    if any(k in joined for k in ["washer", "washing machine", "washing"]):
        return "washing_machine"
    if "microwave" in joined or "oven" in joined:
        return "microwave"
    if any(k in joined for k in ["camera", "dslr", "mirrorless", "lens", "camcorder"]):
        return "camera"
    if any(k in joined for k in ["router", "modem", "wifi", "wi-fi", "mesh"]):
        return "router"
    if any(k in joined for k in ["smartwatch", "smart watch", "wearable", "fitness band", "band"]):
        return "wearable"
    if any(k in joined for k in ["speaker", "soundbar", "headphone", "earbud", "audio", "bluetooth speaker"]):
        return "audio"
    if any(k in joined for k in ["purifier", "air purifier", "water purifier", "ro purifier"]):
        return "purifier"
    if any(k in joined for k in ["mixer", "grinder", "blender", "food processor", "juicer", "chopper", "toaster", "kettle"]):
        return "kitchen_appliance"
    if any(k in joined for k in ["dishwasher", "appliance"]):
        return "appliance"
    return "general"


def _category_from_warranty(warranty: Dict) -> str:
    return infer_product_category(warranty)


def build_product_recommendations(
    user_id: str,
    warranty_id: str,
    region: Optional[str] = None,
    warranty: Optional[Dict] = None,
    predictive: Optional[Dict] = None,
) -> List[ProductRecommendation]:
    warranty = warranty or {}
    predictive = predictive or {}
    band = _risk_band(predictive.get("risk_label"), predictive.get("risk_score"))
    category = _category_from_warranty(warranty)
    reasons = predictive.get("behaviour_reasons") or predictive.get("reasons") or []
    risk_context = "; ".join(str(r) for r in reasons[:2]) if reasons else ""

    care_items = CARE_CATALOG.get(category) or CARE_CATALOG["general"]
    results: List[ProductRecommendation] = []
    for idx, item in enumerate(sorted(care_items, key=lambda i: (i.get("priority", 99), i.get("product_id", "")))[:4]):
        rec: ProductRecommendation = {
          "product_id": item["product_id"],
          "title": item["title"],
          "category": category,
          "region": region,
          "risk_band": band,
          "why": f"{item['why']} {risk_context}".strip(),
          "priority": int(item.get("priority", idx + 1)),
          "cta_label": "View care note",
          "cta_url": None,
        }
        rec["action"] = "general_care"
        rec["description"] = rec["why"]
        rec["reason"] = rec["why"]
        results.append(rec)
    return results


# -------- Product interest events (OEM demand signals) ----------

def _mongo_collection():
    if MongoClient is None:
        return None
    try:
        uri = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
        client = MongoClient(uri, serverSelectionTimeoutMS=500)
        client.server_info()  # trigger connection check
        return client["swh"]["product_interest_events"]
    except Exception:
        return None


def record_product_interest_event(event: Dict):
    event = dict(event)
    event.setdefault("ts", dt.datetime.utcnow().isoformat())
    col = _mongo_collection()
    if col:
        try:
            col.insert_one(event)
            return
        except Exception:
            pass
    os.makedirs("data", exist_ok=True)
    path = os.path.join("data", "product_interest_events.jsonl")
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(event) + "\n")


def _iter_events():
    col = _mongo_collection()
    if col:
        try:
            for doc in col.find({}).limit(1000):
                yield doc
            return
        except Exception:
            pass
    path = os.path.join("data", "product_interest_events.jsonl")
    if not os.path.exists(path):
        return
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            try:
                yield json.loads(line)
            except Exception:
                continue


def aggregate_product_interest(region: Optional[str] = None, risk_band: Optional[str] = None, limit: int = 5):
    counts: Dict[str, Dict] = {}
    for ev in _iter_events() or []:
        if region and ev.get("region") and ev.get("region") != region:
            continue
        if risk_band and ev.get("risk_band") and ev.get("risk_band") != risk_band:
            continue
        pid = ev.get("product_id")
        if not pid:
            continue
        entry = counts.setdefault(pid, {"product_id": pid, "title": ev.get("title") or ev.get("product_id"), "count": 0})
        entry["count"] += 1
    top = sorted(counts.values(), key=lambda x: (-x["count"], x["product_id"]))[:limit]
    return top


def aggregate_product_interest_stats(
    *,
    region: Optional[str] = None,
    risk_band: Optional[str] = None,
    product_id: Optional[str] = None,
    min_cohort: int = 10,
    limit: int = 10,
) -> Dict:
    users = set()
    product_counts: Dict[str, Dict] = {}
    action_counts: Dict[str, int] = {}
    for ev in _iter_events() or []:
        if region and ev.get("region") and ev.get("region") != region:
            continue
        if risk_band and ev.get("risk_band") and ev.get("risk_band") != risk_band:
            continue
        if product_id and ev.get("product_id") != product_id:
            continue
        uid = ev.get("user_id")
        if uid:
            users.add(uid)
        pid = ev.get("product_id")
        if pid:
            entry = product_counts.setdefault(
                pid,
                {
                    "product_id": pid,
                    "title": ev.get("title") or pid,
                    "count": 0,
                    "actions": {},
                    "risk_bands": {},
                },
            )
            entry["count"] += 1
            action = ev.get("action") or "unknown"
            band = ev.get("risk_band") or "unknown"
            entry["actions"][action] = entry["actions"].get(action, 0) + 1
            entry["risk_bands"][band] = entry["risk_bands"].get(band, 0) + 1
            action_counts[action] = action_counts.get(action, 0) + 1
    if len(users) < min_cohort:
        return {
            "status": "suppressed",
            "reason": "minimum cohort threshold not met",
            "min_cohort": min_cohort,
            "cohort_size": len(users),
        }
    top = sorted(product_counts.values(), key=lambda x: (-x["count"], x["product_id"]))[:limit]
    return {
        "status": "ok",
        "min_cohort": min_cohort,
        "cohort_size": len(users),
        "event_count": sum(item["count"] for item in product_counts.values()),
        "action_counts": action_counts,
        "items": top,
        "privacy_note": "Aggregated product-interest signals only; individual customer actions are not exposed.",
    }
