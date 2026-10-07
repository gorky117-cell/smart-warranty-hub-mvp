"""Question packs per product type (batch 3 items 9 and 10).

A pack is a short list of button questions for one product line (AC first, then phone, fridge, washing machine,
geyser, laptop, TV, printer). The dashboard shows 3 at a time, each with a one-line "why we ask" and a Skip
button. Answers feed:
  (a) product-specific care tips and reminders (SWH's own words),
  (b) the reasons behind the care-risk label (no answers -> "Not enough information yet", never "Low risk"),
  (c) anonymous group counts for brands: only answers of customers who agreed, only for groups of 10 or more.

Every question, option, tip and reason here is written by SWH; nothing is a brand's text.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Dict, List, Optional

from sqlalchemy.orm import Session

from ..db_models import QuestionPackAnswerDB, QuestionPackConsentDB, WarrantyDB, WarrantyOwnerDB

SKIP = "skip"
BATCH_SIZE = 3
MIN_GROUP = 10  # brands only ever see counts for groups this large


def _o(value, label, risk=0, reason=None, tip=None, reminder=None):
    return {"value": value, "label": label, "risk": risk, "reason": reason, "tip": tip, "reminder": reminder}


_POWER = {
    "id": "power", "text": "Does the power at home go up and down (lights dim or flicker)?",
    "why": "Voltage swings are a common cause of damage that warranties do not cover.",
    "options": [
        _o("stable", "No, it is stable"),
        _o("fluctuates_protected", "Sometimes, but I use a stabiliser or surge protector",
           tip="Keep using the stabiliser or surge protector; it protects against damage the warranty does not cover."),
        _o("fluctuates_unprotected", "Yes, and I have no stabiliser or surge protector", risk=2,
           reason="Power at home fluctuates and there is no stabiliser or surge protector",
           tip="Use a stabiliser or surge protector: damage from voltage swings is usually not covered by the warranty."),
        _o("not_sure", "Not sure"),
    ],
}


def _problem(extra_options):
    return {
        "id": "problem", "text": "Is anything wrong with it right now?",
        "why": "A problem found early is easier to claim while the warranty lasts.",
        "options": [_o("none", "No, it works fine")] + extra_options,
    }


def _region_question(subject: str) -> Dict:
    return {
        "id": "region", "kind": "place", "text": f"Where is the {subject} used?",
        "why": "Heat, humidity and sea air change how often it needs care.",
        "options": [],  # filled per product from the invoice's city/state, or climate choices
    }


_CLIMATE_OPTIONS = [
    _o("hot", "Hot most of the year"), _o("dry", "Hot and dry or dusty"), _o("humid", "Humid"),
    _o("coastal", "Near the sea"), _o("cold", "Cold winters, mild summers"),
]

PACKS: Dict[str, Dict] = {
    "air_conditioner": {"title": "Your AC", "questions": [
        _region_question("AC"),
        {"id": "ac_hours", "text": "In the hot months, how many hours a day does the AC run?",
         "why": "Long daily use wears the compressor faster, so we can time service reminders.",
         "options": [_o("lt4", "Less than 4 hours"), _o("4to8", "4 to 8 hours"),
                     _o("8to12", "8 to 12 hours", risk=1, reason="Runs 8 to 12 hours a day in summer"),
                     _o("gt12", "More than 12 hours", risk=2, reason="Runs more than 12 hours a day in summer",
                        tip="Heavy summer use: book a service before the hot months and clean the filter every 2 weeks.")]},
        {"id": "ac_last_service", "text": "When was the AC last serviced?",
         "why": "Regular service keeps it cooling well and is often needed for warranty claims.",
         "options": [_o("lt6m", "In the last 6 months"), _o("6to12m", "6 to 12 months ago"),
                     _o("gt12m", "More than a year ago", risk=1, reason="Not serviced for more than a year",
                        reminder={"key": "ac_service", "title": "Time for an AC service",
                                  "message": "Your AC has not been serviced for over a year. Book a service before the hot months."}),
                     _o("never", "Never", risk=2, reason="Never serviced",
                        reminder={"key": "ac_service", "title": "Time for an AC service",
                                  "message": "Your AC has never been serviced. Book a service before the hot months."})]},
        {"id": "ac_service_by", "text": "Who services it?",
         "why": "Some warranties need service by the brand's authorised technicians.",
         "options": [_o("brand", "The brand's service centre"), _o("local", "A local technician", risk=1,
                        reason="Serviced by a local technician (some warranties need the brand's service)",
                        tip="Check your warranty card: some brands only honour claims after authorised service."),
                     _o("nobody", "Nobody yet")]},
        {"id": "ac_filter", "text": "How often is the filter cleaned?",
         "why": "A dirty filter makes the AC work harder and cool less.",
         "options": [_o("2weeks", "Every 2 weeks"), _o("monthly", "Every month"),
                     _o("rarely", "Rarely", risk=1, reason="Filter rarely cleaned",
                        tip="Clean the filter every 2 weeks in summer: rinse it in water and let it dry fully."),
                     _o("never", "Never or not sure", risk=1, reason="Filter not cleaned",
                        tip="Clean the filter every 2 weeks in summer: rinse it in water and let it dry fully.")]},
        _POWER,
        _problem([_o("not_cooling", "Not cooling well", risk=3, reason="Not cooling well right now"),
                  _o("leaking", "Water leaking", risk=2, reason="Water leaking right now"),
                  _o("noise", "Noise or vibration", risk=2, reason="Unusual noise or vibration"),
                  _o("trips", "It trips the power", risk=3, reason="It trips the power")]),
        {"id": "ac_installer", "text": "Who installed it?",
         "why": "Installation by the brand or seller is sometimes needed for the warranty to start.",
         "options": [_o("brand", "The brand's installer"), _o("seller", "The seller's installer"),
                     _o("local", "A local technician", risk=1, reason="Installed by a local technician"),
                     _o("not_sure", "Not sure")]},
    ]},
    "smartphone": {"title": "Your phone", "questions": [
        {"id": "phone_charger", "text": "Which charger do you use?",
         "why": "Poor chargers can damage the battery, which warranties often exclude.",
         "options": [_o("original", "The one that came with it, or the brand's"), _o("rated", "Another good-quality charger"),
                     _o("cheap", "Any cheap charger", risk=1, reason="Uses unbranded chargers",
                        tip="Use the brand's charger or a certified one; cheap chargers can damage the battery.")]},
        {"id": "phone_case", "text": "Does it have a case and screen guard?",
         "why": "Screen and drop damage are usually not covered.",
         "options": [_o("both", "Both"), _o("one", "One of them"),
                     _o("none", "Neither", risk=1, reason="No case or screen guard",
                        tip="A case and screen guard help: drops and cracked screens are usually not covered.")]},
        {"id": "phone_water", "text": "Has it been near water or rain?",
         "why": "Water damage usually voids the warranty, even on water-resistant phones.",
         "options": [_o("no", "No"), _o("splash", "A splash", risk=1, reason="Has been splashed with water"),
                     _o("dropped", "Dropped in water", risk=3, reason="Has been dropped in water")]},
        _problem([_o("battery", "Battery drains fast or swells", risk=2, reason="Battery problem right now"),
                  _o("heat", "Gets very hot", risk=2, reason="Overheats"),
                  _o("screen", "Screen problem", risk=2, reason="Screen problem")]),
        _region_question("phone"),
    ]},
    "fridge": {"title": "Your fridge", "questions": [
        _region_question("fridge"),
        {"id": "fridge_gap", "text": "Is there a gap of a hand's width behind and beside the fridge?",
         "why": "Without space to release heat, the compressor works harder.",
         "options": [_o("yes", "Yes"), _o("no", "No, it is tight against the wall", risk=1,
                        reason="No space behind the fridge for heat to escape",
                        tip="Leave a hand's gap behind and beside the fridge so it can release heat.")]},
        _POWER,
        {"id": "fridge_seal", "text": "Does the door close tightly all round?",
         "why": "A loose seal lets cold air out and strains the compressor.",
         "options": [_o("yes", "Yes"), _o("no", "No, it is loose or cracked", risk=2, reason="Door seal loose or cracked",
                        tip="Ask the brand's service to replace a loose or cracked door seal.")]},
        _problem([_o("not_cooling", "Not cooling well", risk=3, reason="Not cooling well right now"),
                  _o("noise", "Loud noise", risk=2, reason="Unusual noise"),
                  _o("ice", "Ice building up", risk=1, reason="Ice building up")]),
    ]},
    "washing_machine": {"title": "Your washing machine", "questions": [
        {"id": "wm_loads", "text": "How many washes a week?",
         "why": "Heavy use wears the motor and drum bearings sooner.",
         "options": [_o("lt4", "Up to 3"), _o("4to7", "4 to 7"),
                     _o("gt7", "More than 7", risk=1, reason="More than 7 washes a week")]},
        {"id": "wm_water", "text": "Is your water hard (white marks on taps and buckets)?",
         "why": "Hard water leaves scale that damages heaters and drums.",
         "options": [_o("no", "No"), _o("yes", "Yes", risk=1, reason="Hard water",
                        tip="Run an empty hot wash with descaler every month if your water is hard.")]},
        {"id": "wm_level", "text": "Does it shake or move during spin?",
         "why": "An uneven machine strains the drum and motor.",
         "options": [_o("no", "No"), _o("yes", "Yes", risk=2, reason="Shakes or moves during spin",
                        tip="Level the feet so the machine stands firm; shaking strains the drum.")]},
        _POWER,
        _problem([_o("not_draining", "Not draining", risk=2, reason="Not draining"),
                  _o("leaking", "Leaking", risk=2, reason="Leaking"),
                  _o("noise", "Loud noise", risk=2, reason="Unusual noise")]),
        _region_question("washing machine"),
    ]},
    "water_heater": {"title": "Your geyser", "questions": [
        _region_question("geyser"),
        {"id": "geyser_water", "text": "Is your water hard (white marks on taps and buckets)?",
         "why": "Scale shortens the life of the heating element and tank.",
         "options": [_o("no", "No"), _o("yes", "Yes", risk=1, reason="Hard water",
                        tip="Have the geyser descaled once a year if your water is hard.")]},
        {"id": "geyser_service", "text": "When was it last serviced or descaled?",
         "why": "Yearly checks keep the safety valve and element working.",
         "options": [_o("lt12m", "In the last year"), _o("gt12m", "More than a year ago", risk=1,
                        reason="Not serviced for more than a year",
                        reminder={"key": "geyser_service", "title": "Time to check your geyser",
                                  "message": "Your geyser has not been checked for over a year. Book a check before winter."}),
                     _o("never", "Never", risk=1, reason="Never serviced")]},
        {"id": "geyser_on", "text": "Is it left switched on all day?",
         "why": "Running all day wears the element and wastes power.",
         "options": [_o("no", "No, only when needed"), _o("yes", "Yes", risk=1, reason="Left on all day",
                        tip="Switch the geyser on only when needed.")]},
        _problem([_o("leaking", "Leaking", risk=3, reason="Leaking"), _o("trips", "It trips the power", risk=3, reason="Trips the power"),
                  _o("not_heating", "Not heating well", risk=2, reason="Not heating well")]),
    ]},
    "laptop": {"title": "Your laptop", "questions": [
        {"id": "laptop_hours", "text": "How many hours a day is it used?",
         "why": "Long daily use and heat wear the battery and fan.",
         "options": [_o("lt4", "Less than 4"), _o("4to8", "4 to 8"), _o("gt8", "More than 8", risk=1, reason="Used more than 8 hours a day")]},
        {"id": "laptop_surface", "text": "Where is it usually placed while in use?",
         "why": "Soft surfaces block the air vents and overheat it.",
         "options": [_o("desk", "On a desk or table"), _o("soft", "On a bed or lap", risk=1, reason="Used on soft surfaces",
                        tip="Use the laptop on a hard surface so the vents stay clear.")]},
        {"id": "laptop_backup", "text": "Are your important files backed up somewhere else?",
         "why": "Repairs under warranty may wipe the disk.",
         "options": [_o("yes", "Yes"), _o("no", "No", tip="Back up important files before any repair: warranty repairs may wipe the disk.")]},
        _POWER,
        _problem([_o("heat", "Gets very hot or shuts down", risk=2, reason="Overheats"),
                  _o("battery", "Battery does not last", risk=1, reason="Battery problem"),
                  _o("screen", "Screen or keyboard problem", risk=2, reason="Screen or keyboard problem")]),
    ]},
    "tv": {"title": "Your TV", "questions": [
        _POWER,
        {"id": "tv_hours", "text": "How many hours a day is it on?",
         "why": "Long daily use wears the panel and backlight.",
         "options": [_o("lt4", "Less than 4"), _o("4to8", "4 to 8"), _o("gt8", "More than 8", risk=1, reason="On more than 8 hours a day")]},
        {"id": "tv_mount", "text": "Is it wall-mounted?",
         "why": "Wrong mounting can crack the panel, which is usually not covered.",
         "options": [_o("brand", "Yes, by the brand's installer"), _o("other", "Yes, by someone else", risk=1,
                        reason="Wall-mounted by someone other than the brand"), _o("stand", "No, on a stand")]},
        _problem([_o("lines", "Lines, spots or flicker", risk=3, reason="Lines, spots or flicker on the screen"),
                  _o("no_power", "Does not turn on sometimes", risk=2, reason="Power problem"),
                  _o("sound", "Sound problem", risk=1, reason="Sound problem")]),
        _region_question("TV"),
    ]},
    "printer": {"title": "Your printer", "questions": [
        {"id": "printer_often", "text": "How often do you print?",
         "why": "Ink dries in the nozzles when a printer sits unused.",
         "options": [_o("weekly", "Every week"), _o("monthly", "Every month"),
                     _o("rarely", "Rarely", risk=1, reason="Rarely used, so ink can dry",
                        tip="Print a page every week or two so the ink does not dry in the nozzles.")]},
        {"id": "printer_ink", "text": "Which ink do you use?",
         "why": "Non-original ink can void the printhead warranty.",
         "options": [_o("original", "The brand's ink"), _o("other", "Other ink", risk=2, reason="Uses non-original ink",
                        tip="Use the brand's ink: other ink can void the printhead warranty.")]},
        {"id": "printer_dry", "text": "Has the ink ever run out completely?",
         "why": "Printing with empty tanks can damage the printhead.",
         "options": [_o("no", "No"), _o("yes", "Yes", risk=1, reason="Ink has run out completely")]},
        _problem([_o("lines", "Missing lines or faded prints", risk=2, reason="Print quality problem"),
                  _o("jam", "Paper jams", risk=1, reason="Paper jams")]),
        _region_question("printer"),
    ]},
}


def pack_for(product_line: Optional[str]) -> Optional[Dict]:
    return PACKS.get(str(product_line or ""))


def _product_line(warranty) -> Optional[str]:
    from .terms_cache import product_line

    return product_line(getattr(warranty, "model_code", None), getattr(warranty, "product_name", None))


def _place_options(warranty) -> List[Dict]:
    region = (getattr(warranty, "alternatives", None) or {}).get("delivery_region") or {}
    if region.get("state"):
        place = ", ".join(p for p in (region.get("city"), region.get("state")) if p)
        return [_o("invoice_place", f"{place} (from your invoice)"), _o("elsewhere", "Somewhere else")] + _CLIMATE_OPTIONS
    return list(_CLIMATE_OPTIONS)


def questions_for(warranty) -> List[Dict]:
    pack = pack_for(_product_line(warranty))
    if not pack:
        return []
    out = []
    for q in pack["questions"]:
        q = dict(q)
        if q.get("kind") == "place":
            q["options"] = _place_options(warranty)
            if (getattr(warranty, "alternatives", None) or {}).get("delivery_region", {}).get("state"):
                q["why"] = q["why"] + " Choosing the city from your invoice lets us use it for weather tips."
        out.append(q)
    return out


def _public(q: Dict) -> Dict:
    return {"id": q["id"], "text": q["text"], "why": q["why"],
            "options": [{"value": o["value"], "label": o["label"]} for o in q["options"]]}


def answers_for(db: Session, user_id: str, warranty_id: str) -> Dict[str, str]:
    rows = db.query(QuestionPackAnswerDB).filter_by(user_id=user_id, warranty_id=warranty_id).all()
    return {r.question_id: r.answer for r in rows}


def next_batch(db: Session, user_id: str, warranty, limit: int = BATCH_SIZE) -> Dict:
    qs = questions_for(warranty)
    answered = answers_for(db, user_id, warranty.id)
    pending = [q for q in qs if q["id"] not in answered]
    return {
        "pack": _product_line(warranty) if qs else None,
        "title": (pack_for(_product_line(warranty)) or {}).get("title"),
        "questions": [_public(q) for q in pending[:limit]],
        "answered": sum(1 for v in answered.values() if v != SKIP),
        "total": len(qs),
        "share_consent": share_consent(db, user_id),
    }


def record_answer(db: Session, user_id: str, warranty, question_id: str, answer: str) -> Dict:
    """Store one answer (or "skip"). Raises ValueError for an unknown question or option."""
    q = next((q for q in questions_for(warranty) if q["id"] == question_id), None)
    if not q:
        raise ValueError("unknown question")
    if answer != SKIP and answer not in {o["value"] for o in q["options"]}:
        raise ValueError("unknown answer")
    row = db.query(QuestionPackAnswerDB).filter_by(user_id=user_id, warranty_id=warranty.id, question_id=question_id).first()
    if row is None:
        row = QuestionPackAnswerDB(user_id=user_id, warranty_id=warranty.id, pack=_product_line(warranty) or "",
                                   question_id=question_id)
        db.add(row)
    row.answer = answer
    row.created_at = datetime.utcnow()
    # Choosing the invoice's city is the customer's yes to using it for weather tips.
    if q.get("kind") == "place" and answer not in (SKIP, "elsewhere"):
        meta = dict(warranty.alternatives or {})
        region = dict(meta.get("delivery_region") or {})
        if answer == "invoice_place" and region.get("state"):
            from .purchase_details import climate_for

            region["consent"] = True
            meta["delivery_region"] = region
            warranty.climate_zone = warranty.climate_zone or climate_for(region)
        elif answer in {o["value"] for o in _CLIMATE_OPTIONS}:
            warranty.climate_zone = answer
        warranty.alternatives = meta
        db.add(warranty)
    db.commit()
    return {"question_id": question_id, "answer": answer}


def _age_note(purchase_date, today: date) -> Optional[str]:
    if not purchase_date:
        return None
    bought = purchase_date.date() if isinstance(purchase_date, datetime) else purchase_date
    months = (today.year - bought.year) * 12 + today.month - bought.month - (1 if today.day < bought.day else 0)
    if months < 0:
        return None
    when = f"{bought.day} {bought.strftime('%b %Y')}"
    if months < 12:
        age = "less than a year old" if months >= 1 else "less than a month old"
    else:
        years = months // 12
        age = f"about {years} year{'s' if years != 1 else ''} old"
    return f"Bought {when} - {age}."


def care_risk(db: Session, user_id: str, warranty, today: Optional[date] = None) -> Dict:
    """Care-risk label from the customer's answers. With no answers: "Not enough information yet" - never low."""
    today = today or datetime.utcnow().date()
    qs = {q["id"]: q for q in questions_for(warranty)}
    answers = {k: v for k, v in answers_for(db, user_id, warranty.id).items() if v != SKIP and k in qs}
    age_note = _age_note(getattr(warranty, "purchase_date", None), today)
    base = {"age_note": age_note, "answered": len(answers), "total": len(qs), "has_pack": bool(qs)}
    if not answers:
        return {**base, "status": "needs_answers", "label": None, "reasons": [], "tips": [], "reminders": [],
                "text": "Not enough information yet - answer 3 quick questions" if qs
                else "Not enough information yet"}
    points, reasons, tips, reminders = 0, [], [], []
    for qid, value in answers.items():
        option = next((o for o in qs[qid]["options"] if o["value"] == value), None)
        if not option:
            continue
        points += option["risk"]
        if option["reason"]:
            reasons.append((option["risk"], option["reason"]))
        if option["tip"] and option["tip"] not in tips:
            tips.append(option["tip"])
        if option["reminder"] and option["reminder"]["key"] not in {r["key"] for r in reminders}:
            reminders.append(option["reminder"])
    bought = getattr(warranty, "purchase_date", None)
    if bought:
        years = (today - (bought.date() if isinstance(bought, datetime) else bought)).days / 365.25
        if years >= 8:
            points += 2
            reasons.append((2, f"About {int(years)} years old"))
        elif years >= 5:
            points += 1
            reasons.append((1, f"About {int(years)} years old"))
    label = "HIGH" if points >= 5 else ("MEDIUM" if points >= 2 else "LOW")
    words = {"HIGH": "Needs attention", "MEDIUM": "Some things to watch", "LOW": "Looking after it well"}[label]
    reasons = [text for _r, text in sorted(reasons, key=lambda item: -item[0])]
    return {**base, "status": "assessed", "label": label, "text": words,
            "reasons": reasons[:4] or ["Nothing in your answers points to a problem."],
            "tips": tips[:4], "reminders": reminders}


def send_reminders(db: Session, user_id: str, warranty, reminders: List[Dict]) -> int:
    """One notification per reminder kind and product (never repeated)."""
    from .notifications import _notification_exists, create_notification

    sent = 0
    for reminder in reminders:
        ntype = f"care_pack_{reminder['key']}"
        if _notification_exists(db, user_id, warranty.id, ntype):
            continue
        if create_notification(user_id, warranty.id, ntype, reminder["title"], reminder["message"], db=db):
            sent += 1
    return sent


# --- anonymous group counts for brands (consent, groups of 10+) ---------------------------------------------

def share_consent(db: Session, user_id: str) -> Optional[bool]:
    row = db.get(QuestionPackConsentDB, user_id)
    return None if row is None else bool(row.share_anonymous)


def set_share_consent(db: Session, user_id: str, share: bool) -> None:
    row = db.get(QuestionPackConsentDB, user_id)
    if row is None:
        db.add(QuestionPackConsentDB(user_id=user_id, share_anonymous=share, updated_at=datetime.utcnow()))
    else:
        row.share_anonymous = share
        row.updated_at = datetime.utcnow()
    db.commit()


def group_counts(db: Session, *, brand: str, pack: str, question_id: str) -> Dict:
    """Counts per answer for one brand, product type and question: only customers who agreed to share, one answer
    per customer, skips left out, and nothing at all unless at least MIN_GROUP customers are in the group."""
    from sqlalchemy import func

    q = next((q for q in PACKS.get(pack, {}).get("questions", []) if q["id"] == question_id), None)
    if not q or q.get("kind") == "place":
        return {"available": False, "reason": "unknown question"}  # places are never shared
    rows = (
        db.query(QuestionPackAnswerDB.user_id, QuestionPackAnswerDB.answer)
        .join(QuestionPackConsentDB, QuestionPackConsentDB.user_id == QuestionPackAnswerDB.user_id)
        .join(WarrantyDB, WarrantyDB.id == QuestionPackAnswerDB.warranty_id)
        .join(WarrantyOwnerDB, (WarrantyOwnerDB.warranty_id == WarrantyDB.id)
              & (WarrantyOwnerDB.user_id == QuestionPackAnswerDB.user_id))
        .filter(QuestionPackConsentDB.share_anonymous.is_(True), QuestionPackAnswerDB.pack == pack,
                QuestionPackAnswerDB.question_id == question_id, QuestionPackAnswerDB.answer != SKIP,
                func.lower(WarrantyDB.brand) == brand.lower())
        .order_by(QuestionPackAnswerDB.created_at.desc())
        .all()
    )
    latest: Dict[str, str] = {}
    for user, answer in rows:
        latest.setdefault(user, answer)  # one answer per customer (their latest)
    if len(latest) < MIN_GROUP:
        return {"available": False, "reason": f"fewer than {MIN_GROUP} customers"}
    labels = {o["value"]: o["label"] for o in q["options"]}
    counts: Dict[str, int] = {}
    for answer in latest.values():
        counts[labels.get(answer, answer)] = counts.get(labels.get(answer, answer), 0) + 1
    return {"available": True, "question": q["text"], "customers": len(latest), "counts": counts}
