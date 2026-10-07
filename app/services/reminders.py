"""Product-specific care reminders (run 3, item 10).

A care reminder is sent only when the brand's own text gives an interval ("Clean the filter every two
weeks", "Print a page at least once a month"): from the saved care guides (manual/FAQ quotes). Tips without
an interval never become reminders - we do not invent how often to do something.

Limits:
- one reminder per tip per interval (and none while the previous one is still unread);
- no care reminders for an expired warranty or a product with no warranty dates (the expiry notices cover
  expired products: one "Warranty ended" notice, see notifications.create_expiry_notifications);
- at most REMINDER_MAX_PER_DAY reminders per user per day, shared with expiry reminders, and at most
  REMINDER_CARE_MAX_PER_WEEK care reminders per user per week.
"""
from __future__ import annotations

import os
import re
from datetime import date, datetime, timedelta
from typing import Dict, Optional

from sqlalchemy.orm import Session

from ..db_models import CareGuideDB, NotificationDB, WarrantyDB, WarrantyOwnerDB
from . import care_guides
from .notifications import _product_label, create_notification, reminder_daily_cap, reminders_today
from .warranty_status import compute_warranty_status

_N = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
      "twelve": 12, "a": 1, "an": 1}
_UNIT_DAYS = {"day": 1, "week": 7, "fortnight": 14, "month": 30, "year": 365}


def interval_days(text: str) -> Optional[int]:
    """Days between reminders as the text states it; None when it gives no interval."""
    low = (text or "").lower()
    m = re.search(r"\bevery\s+(\d+|one|two|three|four|five|six|seven|eight|nine|ten|twelve)?\s*"
                  r"(day|week|fortnight|month|year)s?\b", low)
    if m:
        qty = m.group(1)
        n = int(qty) if qty and qty.isdigit() else _N.get(qty or "one", 1)
        return n * _UNIT_DAYS[m.group(2)]
    m = re.search(r"\b(?:once|twice)\s+(?:a|an|per|every)\s+(day|week|fortnight|month|year)\b", low)
    if m:
        days = _UNIT_DAYS[m.group(1)]
        return max(1, days // 2) if "twice" in m.group(0) else days
    m = re.search(r"\b(daily|weekly|fortnightly|monthly|yearly|annually)\b", low)
    if m:
        return {"daily": 1, "weekly": 7, "fortnightly": 14, "monthly": 30, "yearly": 365, "annually": 365}[m.group(1)]
    return None


def care_weekly_cap() -> int:
    try:
        return max(1, int(os.getenv("REMINDER_CARE_MAX_PER_WEEK", "2")))
    except ValueError:
        return 2


def _care_sent_since(db: Session, user_id: str, since: datetime, ntype: Optional[str] = None, warranty_id: Optional[str] = None):
    q = db.query(NotificationDB).filter(
        NotificationDB.user_id == user_id, NotificationDB.audience == "user", NotificationDB.created_at >= since,
        NotificationDB.type.like("care_%"),
    )
    if ntype:
        q = q.filter(NotificationDB.type == ntype)
    if warranty_id:
        q = q.filter(NotificationDB.warranty_id == warranty_id)
    return q


def refresh_care_reminders(db: Session, today: Optional[date] = None) -> Dict[str, int]:
    today = today or datetime.utcnow().date()
    now = datetime.utcnow() if today == datetime.utcnow().date() else datetime.combine(today, datetime.min.time())
    stats = {"created": 0, "no_interval": 0, "expired_or_unknown": 0, "held_back": 0}
    guides = db.query(CareGuideDB).all()
    if not guides:
        stats["pack_created"] = _pack_reminders(db, now, stats)
        return stats
    for owner in db.query(WarrantyOwnerDB).all():
        w = db.query(WarrantyDB).filter_by(id=owner.warranty_id).first()
        if not w:
            continue
        found = care_guides.find(db, company=w.brand, model_code=w.model_code, product_name=w.product_name)
        if not found:
            continue
        status = compute_warranty_status(purchase_date=w.purchase_date, coverage_months=w.coverage_months,
                                         expiry_date=w.expiry_date, today=today)["status"]
        if status not in ("active", "expiring_soon"):
            stats["expired_or_unknown"] += 1
            continue
        label = _product_label(w, w.id)
        from . import reuse_policy

        for guide in found:
            if not reuse_policy.allows(guide.company, reuse_policy.SUMMARY_OK):
                continue  # the tip text is condensed from the brand's text: only with the brand's permission
            for i, tip in enumerate(guide.tips or []):
                days = interval_days(tip.get("quote", ""))
                if not days:
                    stats["no_interval"] += 1
                    continue
                ntype = f"care_{guide.id}_{i}"
                if _care_sent_since(db, owner.user_id, now - timedelta(days=days), ntype, w.id).first():
                    continue  # already reminded within this interval
                if (_care_sent_since(db, owner.user_id, now - timedelta(days=7)).count() >= care_weekly_cap()
                        or reminders_today(db, owner.user_id) >= reminder_daily_cap()):
                    stats["held_back"] += 1
                    continue
                kind = care_guides.SOURCE_KINDS.get(guide.source_kind, "user manual")
                made = create_notification(
                    db=db, user_id=owner.user_id, warranty_id=w.id, type=ntype,
                    title=f"Care reminder: {label}",
                    message=f"{tip['text']} (From {guide.company}'s {kind}.)",
                    severity="info",
                )
                if made:
                    stats["created"] += 1
    stats["pack_created"] = _pack_reminders(db, now, stats)
    return stats


def _pack_reminders(db: Session, now: datetime, stats: Dict[str, int]) -> int:
    """Maintenance reminders from approved question-and-care packs (SWH wording, "about ..." intervals), with the
    same limits: once per interval, weekly and daily caps, none for expired or undated products."""
    from . import care_packs

    created = 0
    for owner in db.query(WarrantyOwnerDB).all():
        w = db.query(WarrantyDB).filter_by(id=owner.warranty_id).first()
        if not w:
            continue
        pack = care_packs.customer_pack(db, w)
        if not pack:
            continue
        status = compute_warranty_status(purchase_date=w.purchase_date, coverage_months=w.coverage_months,
                                         expiry_date=w.expiry_date, today=now.date())["status"]
        if status not in ("active", "expiring_soon"):
            continue
        label = _product_label(w, w.id)
        for reminder in pack["reminders"]:
            ntype = f"care_pack_{pack['product_type']}_{reminder['id']}"
            if _care_sent_since(db, owner.user_id, now - timedelta(days=int(reminder["interval_days"])), ntype, w.id).first():
                continue
            if (_care_sent_since(db, owner.user_id, now - timedelta(days=7)).count() >= care_weekly_cap()
                    or reminders_today(db, owner.user_id) >= reminder_daily_cap()):
                stats["held_back"] += 1
                continue
            made = create_notification(
                db=db, user_id=owner.user_id, warranty_id=w.id, type=ntype,
                title=f"Care reminder: {label}",
                message=f"{reminder['text']} ({reminder['interval_text'].capitalize()}. {reminder['note']})",
                severity="info",
            )
            if made:
                created += 1
    return created
