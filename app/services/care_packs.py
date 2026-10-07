"""Question and care packs: one data file per product type (data/care_packs/<type>.json), no code per product.

A pack has behaviour questions (button answers, Skip, a one-line "why we ask", asked 3 at a time), care tips
(priority, trigger, "why"; safety tips first for electric, gas and battery products), maintenance reminders
("about ..." + "check your manual"), risk factors (answers that raise or lower risk, with reasons), the usual
warranty structure (no numbers - "check your warranty card") and exclusions to look for.

Every pack file ships as "draft". An admin reviews, edits and approves it (table `care_packs`, audit-logged);
customers see only approved packs and otherwise keep the general tips. Answers (table `care_pack_answers`)
feed care tips, reminders, risk reasons and anonymous group counts (only users who allow analytics, and only
groups of at least OEM_TELEMETRY_MIN_COHORT people, default 10).
"""
from __future__ import annotations

import copy
import json
import re
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

PACK_DIR = Path(__file__).resolve().parents[2] / "data" / "care_packs"
DRAFT, APPROVED = "draft", "approved"
PRIORITIES = {"HIGH": 1, "MEDIUM": 2, "LOW": 3}
HAZARDS = {"electric", "gas", "battery"}
QUESTIONS_PER_ROUND = 3


# --- loading and validation -----------------------------------------------------------------------------------

@lru_cache(maxsize=1)
def _files() -> Dict[str, Dict[str, Any]]:
    packs = {}
    for path in sorted(PACK_DIR.glob("*.json")):
        pack = json.loads(path.read_text(encoding="utf-8"))
        packs[pack["product_type"]] = pack
    return packs


def reset_cache() -> None:
    _files.cache_clear()


def product_types() -> List[str]:
    return list(_files())


def file_pack(product_type: str) -> Optional[Dict[str, Any]]:
    pack = _files().get(product_type)
    return copy.deepcopy(pack) if pack else None


def validate(pack: Dict[str, Any]) -> List[str]:
    """Problems with a pack's shape and content rules; empty when it is fine."""
    problems: List[str] = []
    for key in ("product_type", "label", "status", "hazards", "match", "questions", "care_tips", "reminders",
                "risk_factors", "warranty_structure", "exclusions_to_look_for"):
        if key not in pack:
            problems.append(f"missing part: {key}")
    if problems:
        return problems
    if pack["status"] not in (DRAFT, APPROVED):
        problems.append("status must be draft or approved")
    if not set(pack["hazards"]) <= HAZARDS:
        problems.append(f"hazards must be among {sorted(HAZARDS)}")
    questions = pack["questions"]
    if not 6 <= len(questions) <= 7:
        problems.append("6-7 questions needed")
    qids = set()
    for q in questions:
        if not all(q.get(k) for k in ("id", "text", "why", "answers")):
            problems.append(f"question {q.get('id')} needs id, text, why and answers")
            continue
        qids.add(q["id"])
        if not 2 <= len(q["answers"]) <= 5 or not all(a.get("value") and a.get("label") for a in q["answers"]):
            problems.append(f"question {q['id']}: 2-5 button answers with value and label")
    answer_values = {q["id"]: {a["value"] for a in q["answers"]} for q in questions if q.get("answers")}
    tips = pack["care_tips"]
    if not 6 <= len(tips) <= 10:
        problems.append("6-10 care tips needed")
    for tip in tips:
        if not all(tip.get(k) for k in ("id", "text", "why", "priority", "trigger")):
            problems.append(f"tip {tip.get('id')} needs id, text, why, priority and trigger")
            continue
        if tip["priority"] not in PRIORITIES:
            problems.append(f"tip {tip['id']}: priority HIGH, MEDIUM or LOW")
        for qid, values in (tip["trigger"].get("answers") or {}).items():
            if qid not in answer_values or not set(values) <= answer_values[qid]:
                problems.append(f"tip {tip['id']}: trigger names an unknown question or answer ({qid})")
    if pack["hazards"]:
        if not tips or not tips[0].get("safety"):
            problems.append("electric, gas and battery products list safety tips first")
        seen_other = False
        for tip in tips:
            if not tip.get("safety"):
                seen_other = True
            elif seen_other:
                problems.append(f"safety tip {tip.get('id')} must come before the other tips")
    for reminder in pack["reminders"]:
        if not all(reminder.get(k) for k in ("id", "text", "interval_days", "interval_text", "note")):
            problems.append(f"reminder {reminder.get('id')} needs id, text, interval_days, interval_text and note")
        elif not str(reminder["interval_text"]).lower().startswith("about"):
            problems.append(f"reminder {reminder['id']}: interval is phrased as 'about ...'")
        elif "manual" not in str(reminder["note"]).lower():
            problems.append(f"reminder {reminder['id']}: note says to check the manual")
    if not pack["reminders"]:
        problems.append("at least one maintenance reminder")
    for risk in pack["risk_factors"]:
        if risk.get("effect") not in ("raise", "lower") or not risk.get("reason"):
            problems.append(f"risk factor for {risk.get('question')} needs effect raise/lower and a reason")
        elif risk.get("question") not in answer_values or not set(risk.get("answers") or []) <= answer_values[risk["question"]]:
            problems.append(f"risk factor names an unknown question or answer ({risk.get('question')})")
    if not pack["risk_factors"]:
        problems.append("at least one risk factor")
    for part in pack["warranty_structure"]:
        if not part.get("part") or "warranty card" not in str(part.get("note", "")).lower():
            problems.append(f"warranty part {part.get('part')}: note must say to check the warranty card")
        if re.search(r"\d", f"{part.get('part', '')} {part.get('note', '')}"):
            problems.append(f"warranty part {part.get('part')}: no numbers")
    if not pack["warranty_structure"]:
        problems.append("usual warranty structure needed")
    if not pack["exclusions_to_look_for"]:
        problems.append("exclusions to look for needed")
    for item in pack["exclusions_to_look_for"]:
        if re.search(r"\d", str(item)):
            problems.append(f"exclusion '{item}': no numbers")
    problems += content_rule_problems(pack)
    return problems


# Content rules: no brand names, no repair instructions, no warranty periods.
_REPAIR = re.compile(
    r"\b(unscrew|screwdriver|disassembl\w*|take (?:it |the \w+ )?apart|solder\w*|rewir\w*|re-?wire|"
    r"refill(?:ing)? the gas|recharg\w* the gas|replace the (?:capacitor|fuse|element|compressor|board|thermostat|battery cells?)|"
    r"open the (?:unit|cover|casing|back panel|battery) (?:and|to)|short[- ]circuit the)\b",
    re.I,
)
_NEGATED = re.compile(r"^\s*(?:don't|do not|never|avoid)\b", re.I)
_WARRANTY_NUMBER = re.compile(r"\d+\s*(?:-|to)?\s*\d*\s*(?:years?|yrs?|months?)\b[^.]{0,40}warrant|warrant\w*[^.]{0,40}\d+\s*(?:years?|months?)", re.I)


def _texts(pack: Dict[str, Any]) -> List[str]:
    out = [pack.get("label", "")]
    for q in pack.get("questions") or []:
        out += [q.get("text", ""), q.get("why", "")] + [a.get("label", "") for a in q.get("answers") or []]
    for tip in pack.get("care_tips") or []:
        out += [tip.get("text", ""), tip.get("why", "")]
    for r in pack.get("reminders") or []:
        out += [r.get("text", ""), r.get("interval_text", ""), r.get("note", "")]
    out += [r.get("reason", "") for r in pack.get("risk_factors") or []]
    out += [f"{p.get('part', '')}. {p.get('note', '')}" for p in pack.get("warranty_structure") or []]
    out += list(pack.get("exclusions_to_look_for") or [])
    return [t for t in out if t]


def content_rule_problems(pack: Dict[str, Any]) -> List[str]:
    from .brand_registry import find_brands

    problems = []
    for text in _texts(pack):
        for sentence in re.split(r"(?<=[.;])\s+", text):
            if _REPAIR.search(sentence) and not _NEGATED.search(sentence):
                problems.append(f"repair instruction: '{sentence[:80]}'")
        brands = find_brands(text)
        if brands:
            problems.append(f"brand name {brands} in '{text[:80]}'")
        if _WARRANTY_NUMBER.search(text):
            problems.append(f"warranty period in '{text[:80]}'")
    return problems


# --- state: approval and edits (database) -----------------------------------------------------------------------

def _row(db: Session, product_type: str):
    from ..db_models import CarePackDB

    try:
        return db.query(CarePackDB).filter_by(product_type=product_type).first()
    except Exception:
        db.rollback()
        return None


def effective(db: Session, product_type: str) -> Optional[Dict[str, Any]]:
    """The pack as reviewed: an admin-edited copy if there is one, else the file; status from the database."""
    pack = file_pack(product_type)
    if pack is None:
        return None
    row = _row(db, product_type)
    if row is not None:
        if row.content:
            pack = json.loads(row.content)
        pack["status"] = row.status
        pack["approved_by"], pack["approved_at"] = row.approved_by, row.approved_at.isoformat() if row.approved_at else None
    else:
        pack["status"] = DRAFT  # a file is never approved by itself
    return pack


def _audit(action: str, detail: str) -> None:
    from .audit import log_action

    log_action(action, detail)


def save_edit(db: Session, product_type: str, content: Dict[str, Any], *, admin: str) -> Dict[str, Any]:
    """Store an admin's edited pack; it goes back to draft until approved again."""
    from ..db_models import CarePackDB

    if file_pack(product_type) is None:
        raise ValueError("unknown product type")
    content = dict(content)
    content["product_type"], content["status"] = product_type, DRAFT
    problems = validate(content)
    if problems:
        raise ValueError("; ".join(problems[:5]))
    row = _row(db, product_type) or CarePackDB(product_type=product_type)
    row.content, row.status, row.updated_by, row.updated_at = json.dumps(content, ensure_ascii=False), DRAFT, admin, datetime.utcnow()
    row.approved_by = row.approved_at = None
    db.add(row)
    db.commit()
    _audit("care_pack_edit", f"type={product_type} by={admin}")
    return effective(db, product_type)


def set_status(db: Session, product_type: str, status: str, *, admin: str) -> Dict[str, Any]:
    from ..db_models import CarePackDB

    if status not in (DRAFT, APPROVED):
        raise ValueError("status must be draft or approved")
    pack = effective(db, product_type)
    if pack is None:
        raise ValueError("unknown product type")
    problems = validate({**pack, "status": status})
    if status == APPROVED and problems:
        raise ValueError("cannot approve: " + "; ".join(problems[:5]))
    row = _row(db, product_type) or CarePackDB(product_type=product_type)
    row.status, row.updated_by, row.updated_at = status, admin, datetime.utcnow()
    row.approved_by, row.approved_at = (admin, datetime.utcnow()) if status == APPROVED else (None, None)
    db.add(row)
    db.commit()
    _audit(f"care_pack_{'approve' if status == APPROVED else 'unapprove'}", f"type={product_type} by={admin}")
    return effective(db, product_type)


def audit_log(db: Session, product_type: str, limit: int = 50) -> List[Dict[str, Any]]:
    from ..db_models import AuditLogDB

    rows = (
        db.query(AuditLogDB)
        .filter(AuditLogDB.action.like("care_pack_%"), AuditLogDB.detail.like(f"type={product_type} %"))
        .order_by(AuditLogDB.created_at.desc())
        .limit(limit)
        .all()
    )
    return [{"action": r.action, "detail": r.detail, "at": r.created_at.isoformat() if r.created_at else None} for r in rows]


# --- matching a customer's product ------------------------------------------------------------------------------

def match_type(product_name: Optional[str], model_code: Optional[str]) -> Optional[str]:
    """The pack for a product: the longest keyword found in the product name wins; else the product line."""
    from .terms_cache import product_line

    text = f" {(product_name or '').lower()} {(model_code or '').lower()} "
    best: Tuple[int, Optional[str]] = (0, None)
    for ptype, pack in _files().items():
        for keyword in (pack.get("match") or {}).get("keywords") or []:
            if re.search(rf"(?<![a-z0-9]){re.escape(keyword.lower())}(?![a-z0-9])", text) and len(keyword) > best[0]:
                best = (len(keyword), ptype)
    if best[1]:
        return best[1]
    line = product_line(model_code, product_name)
    for ptype, pack in _files().items():
        if line and line in ((pack.get("match") or {}).get("lines") or []):
            return ptype
    return None


def customer_pack(db: Session, warranty) -> Optional[Dict[str, Any]]:
    """The approved pack for this product, or None (customers then keep the general tips)."""
    ptype = match_type(getattr(warranty, "product_name", None), getattr(warranty, "model_code", None))
    pack = effective(db, ptype) if ptype else None
    return pack if pack and pack.get("status") == APPROVED else None


# --- answers ---------------------------------------------------------------------------------------------------

def answers_for(db: Session, user_id: str, warranty_id: str) -> Dict[str, str]:
    from ..db_models import CarePackAnswerDB

    rows = db.query(CarePackAnswerDB).filter_by(user_id=user_id, warranty_id=warranty_id).all()
    return {r.question_id: r.answer for r in rows}


def next_questions(db: Session, user_id: str, warranty, n: int = QUESTIONS_PER_ROUND) -> Dict[str, Any]:
    pack = customer_pack(db, warranty)
    if not pack:
        return {"product_type": None, "questions": []}
    answered = answers_for(db, user_id, warranty.id)
    todo = [q for q in pack["questions"] if q["id"] not in answered][:n]
    return {
        "product_type": pack["product_type"], "label": pack["label"],
        "questions": [{"id": q["id"], "text": q["text"], "why": q["why"], "answers": q["answers"], "can_skip": True} for q in todo],
        "answered": len(answered), "total": len(pack["questions"]),
    }


def record_answer(db: Session, user_id: str, warranty, question_id: str, answer: str) -> Dict[str, Any]:
    """Save one answer; "skip" is kept too so the question is not asked again."""
    from ..db_models import CarePackAnswerDB

    pack = customer_pack(db, warranty)
    if not pack:
        raise ValueError("no questions for this product")
    question = next((q for q in pack["questions"] if q["id"] == question_id), None)
    if question is None:
        raise ValueError("unknown question")
    if answer != "skip" and answer not in {a["value"] for a in question["answers"]}:
        raise ValueError("unknown answer")
    row = db.query(CarePackAnswerDB).filter_by(user_id=user_id, warranty_id=warranty.id, question_id=question_id).first()
    if row is None:
        row = CarePackAnswerDB(user_id=user_id, warranty_id=warranty.id, product_type=pack["product_type"], question_id=question_id)
    row.answer, row.created_at = answer, datetime.utcnow()
    db.add(row)
    db.commit()
    return {"saved": True, "question_id": question_id, "answer": answer}


def _triggered(trigger: Dict[str, Any], answers: Dict[str, str], months_owned: Optional[int]) -> bool:
    if trigger.get("always"):
        return True
    if trigger.get("answers") and any(answers.get(q) in values for q, values in trigger["answers"].items()):
        return True
    if trigger.get("months_owned_at_least") is not None and months_owned is not None:
        return months_owned >= int(trigger["months_owned_at_least"])
    return False


def insights(db: Session, user_id: str, warranty, today=None) -> Dict[str, Any]:
    """Care tips (safety first, then by priority), reminders, risk reasons and what to look for in the terms."""
    pack = customer_pack(db, warranty)
    if not pack:
        return {"product_type": None}
    answers = answers_for(db, user_id, warranty.id)
    months_owned = None
    purchase = getattr(warranty, "purchase_date", None)
    if purchase:
        now = today or datetime.utcnow()
        months_owned = (now.year - purchase.year) * 12 + now.month - purchase.month
    tips = [t for t in pack["care_tips"] if _triggered(t["trigger"], answers, months_owned)]
    tips.sort(key=lambda t: (0 if t.get("safety") else 1, PRIORITIES[t["priority"]]))
    risks = [{"effect": r["effect"], "reason": r["reason"]} for r in pack["risk_factors"]
             if answers.get(r["question"]) in r["answers"]]
    return {
        "product_type": pack["product_type"], "label": pack["label"],
        "care_tips": [{"id": t["id"], "text": t["text"], "why": t["why"], "priority": t["priority"],
                       "safety": bool(t.get("safety"))} for t in tips],
        "reminders": pack["reminders"],
        "risk_reasons": risks,
        "warranty_structure": pack["warranty_structure"],
        "exclusions_to_look_for": pack["exclusions_to_look_for"],
    }


def group_counts(db: Session, product_type: str, min_group: Optional[int] = None) -> Dict[str, Any]:
    """Anonymous answer counts per question, only from people who allow analytics, and only for questions answered
    by at least `min_group` such people (default OEM_TELEMETRY_MIN_COHORT, 10). Skips are not counted."""
    from ..db_models import CarePackAnswerDB, UserDB
    from .telemetry_intelligence import _MIN_OEM_COHORT

    min_group = max(int(min_group or _MIN_OEM_COHORT), 10)
    consenting = {u for (u,) in db.query(UserDB.username).filter(UserDB.consent_analytics == 1).all()}
    per_question: Dict[str, Dict[str, set]] = {}
    for row in db.query(CarePackAnswerDB).filter_by(product_type=product_type).all():
        if row.answer == "skip" or row.user_id not in consenting:
            continue
        per_question.setdefault(row.question_id, {}).setdefault(row.answer, set()).add(row.user_id)
    out = {}
    for qid, by_answer in per_question.items():
        people = set().union(*by_answer.values())
        if len(people) >= min_group:
            out[qid] = {answer: len(users) for answer, users in by_answer.items()}
    return {"product_type": product_type, "min_group": min_group, "questions": out}
