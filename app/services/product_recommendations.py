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


def _category_from_warranty(warranty: Dict) -> str:
    pt = str(warranty.get("product_type") or "").lower()
    name = (warranty.get("product_name") or "").lower()
    model = (warranty.get("model_code") or "").lower()
    if "phone" in name or "phone" in pt or "galaxy" in name or "iphone" in name or "sm-" in model:
        return "smartphone"
    if "laptop" in name or "notebook" in name or "laptop" in pt:
        return "laptop"
    if "ev" in name or "ev" in pt or "battery" in name:
        return "ev"
    if any(k in name for k in ["fridge", "washer", "ac", "dishwasher", "appliance"]):
        return "appliance"
    return "general"


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
    why_txt = "; ".join(reasons[:2]) if reasons else f"Risk band: {band}"

    def match_catalog(item: Dict) -> bool:
        if item.get("category") not in (category, "general"):
            return False
        min_band = item.get("min_risk_band")
        if min_band and _RISK_ORDER.get(band, 0) < _RISK_ORDER.get(min_band, 0):
            return False
        allowed_regions = item.get("supported_regions")
        if allowed_regions and region and region not in allowed_regions:
            return False
        return True

    filtered = [item for item in PRODUCT_CATALOG if match_catalog(item)]
    if not filtered:
        filtered = [item for item in PRODUCT_CATALOG if item.get("category") == "general"]

    filtered = sorted(filtered, key=lambda i: (i.get("priority", 99), i.get("product_id", "")))
    filtered = filtered[:6]

    results: List[ProductRecommendation] = []
    for idx, item in enumerate(filtered):
        rec: ProductRecommendation = {
          "product_id": item["product_id"],
          "title": item["title"],
          "category": item["category"],
          "region": region,
          "risk_band": band,
          "why": why_txt,
          "priority": int(item.get("priority", idx + 1)),
          "cta_label": "View options",
          "cta_url": None,
        }
        # Backward compatibility fields for UI renderers
        rec["action"] = item.get("tags", ["view"])[0] if item.get("tags") else item.get("category", "view")
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
