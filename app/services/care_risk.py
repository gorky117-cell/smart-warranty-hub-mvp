"""What the customer sees in place of a risk rating (batch 3 item 10, revised after the owner's review of PR #3).

Question packs (questions, tips, reminders, anonymous counts, draft/approve) are owned by the packs work on another
branch (`desktop/batch-3`, `services/care_packs.py`). This module only decides the wording, and never says
"Low risk" without answers:
- an APPROVED pack has questions for this product and nothing is answered yet:
  "Not enough information yet - answer 3 quick questions";
- no approved pack (or no packs module at all): "We can't rate this yet.";
- answers exist: the packs module's own label and reasons are passed through.
An age note from the purchase date is always added when the date is known.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Dict, Optional

from sqlalchemy.orm import Session

NEEDS_ANSWERS_TEXT = "Not enough information yet - answer 3 quick questions"
CANNOT_RATE_TEXT = "We can't rate this yet."


def _packs():
    try:
        from . import care_packs  # present once the packs branch is merged
    except ImportError:
        return None
    return care_packs


def approved_pack(db: Session, warranty) -> Optional[Dict]:
    """The approved question pack for this product, if one exists and has questions."""
    packs = _packs()
    if packs is None or not hasattr(packs, "customer_pack"):
        return None
    try:
        pack = packs.customer_pack(db, warranty)
    except Exception:
        db.rollback()
        return None
    return pack if pack and pack.get("questions") else None


def age_note(purchase_date, today: Optional[date] = None) -> Optional[str]:
    if not purchase_date:
        return None
    today = today or datetime.utcnow().date()
    bought = purchase_date.date() if isinstance(purchase_date, datetime) else purchase_date
    months = (today.year - bought.year) * 12 + today.month - bought.month - (1 if today.day < bought.day else 0)
    if months < 0:
        return None
    if months < 1:
        age = "less than a month old"
    elif months < 12:
        age = "less than a year old"
    else:
        years = months // 12
        age = f"about {years} year{'s' if years != 1 else ''} old"
    return f"Bought {bought.day} {bought.strftime('%b %Y')} - {age}."


def summary(db: Session, user_id: str, warranty, today: Optional[date] = None) -> Dict:
    base = {"age_note": age_note(getattr(warranty, "purchase_date", None), today), "label": None, "reasons": []}
    pack = approved_pack(db, warranty)
    if not pack:
        return {**base, "status": "cannot_rate", "text": CANNOT_RATE_TEXT, "has_pack": False}
    packs = _packs()
    answered = {}
    try:
        answered = {k: v for k, v in packs.answers_for(db, user_id, warranty.id).items() if v != "skip"}
    except Exception:
        db.rollback()
    if not answered:
        return {**base, "status": "needs_answers", "text": NEEDS_ANSWERS_TEXT, "has_pack": True}
    try:
        insights = packs.insights(db, user_id, warranty) or {}
    except Exception:
        db.rollback()
        insights = {}
    if "risk_reasons" not in insights:
        return {**base, "status": "needs_answers", "text": NEEDS_ANSWERS_TEXT, "has_pack": True}
    label, reasons = label_from_reasons(insights.get("risk_reasons") or [])
    return {**base, "status": "assessed", "label": label, "text": TEXTS[label], "has_pack": True, "reasons": reasons}


TEXTS = {"HIGH": "Needs attention", "MEDIUM": "Some things to watch", "LOW": "Looking after it well"}


def label_from_reasons(risk_reasons) -> tuple:
    """The packs module returns matched risk factors as {"effect": "raise"|"lower", "reason"} (its "label" is the
    product type's name, not a rating). 3+ raising factors -> HIGH, 1-2 -> MEDIUM, none -> LOW; raising reasons
    are listed first."""
    raising = [r.get("reason") for r in risk_reasons if isinstance(r, dict) and r.get("effect") == "raise" and r.get("reason")]
    lowering = [r.get("reason") for r in risk_reasons if isinstance(r, dict) and r.get("effect") == "lower" and r.get("reason")]
    label = "HIGH" if len(raising) >= 3 else ("MEDIUM" if raising else "LOW")
    reasons = (raising + lowering)[:4] or ["Nothing in your answers points to a problem."]
    return label, reasons
