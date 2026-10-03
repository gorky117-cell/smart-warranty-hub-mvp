"""Recalculated expiry dates never trigger notifications (fix run B11).

A SQLAlchemy `before_flush` hook watches saved warranties. When the effective expiry (stored
`expiry_date`, else purchase date + coverage months) of an **existing** warranty changes, every reminder
stage that is already due under the new date (30d/7d/today/expired, per EXPIRY_REMINDER_STAGE_DAYS) is
added to `alternatives["expiry_suppressed_types"]`, and the change is logged in
`alternatives["expiry_recalculated"]`. `notifications.create_expiry_notifications` skips suppressed types,
so only stages reached later by the passage of time can fire. Expiry reminders send no e-mail.
A warranty's first expiry (no previous value) is not a recalculation and is untouched.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import List, Optional

from sqlalchemy import event, inspect
from sqlalchemy.orm import Session

_WATCHED = ("expiry_date", "purchase_date", "coverage_months")


def _as_date(value) -> Optional[date]:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return None


def _effective_expiry(expiry, purchase, coverage) -> Optional[date]:
    exp = _as_date(expiry)
    if exp:
        return exp
    start = _as_date(purchase)
    if start and coverage:
        try:
            months = int(coverage)
        except (TypeError, ValueError):
            return None
        year = start.year + (start.month - 1 + months) // 12
        month = (start.month - 1 + months) % 12 + 1
        leap = year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)
        day = min(start.day, [31, 29 if leap else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31][month - 1])
        return date(year, month, day)
    return None


def due_stage_types(expiry: date, today: Optional[date] = None) -> List[str]:
    from .notifications import _parse_expiry_stages

    days_left = (expiry - (today or date.today())).days
    types = [f"expiry_{stage}d" for stage in _parse_expiry_stages() if days_left <= stage]
    if days_left == 0:
        types.append("expiry_due")
    if days_left < 0:
        types.append("expiry_expired")
    return types


def _old_value(state, name):
    history = state.attrs[name].history
    if history.deleted:
        return history.deleted[0]
    return state.attrs[name].value


def _before_flush(session: Session, _context, _instances) -> None:
    from ..db_models import WarrantyDB

    for obj in list(session.dirty):
        if not isinstance(obj, WarrantyDB):
            continue
        state = inspect(obj)
        if not any(state.attrs[name].history.has_changes() for name in _WATCHED):
            continue
        old = _effective_expiry(*(_old_value(state, name) for name in _WATCHED))
        new = _effective_expiry(obj.expiry_date, obj.purchase_date, obj.coverage_months)
        if not old or not new or old == new:
            continue
        meta = dict(obj.alternatives or {})
        suppressed = set(meta.get("expiry_suppressed_types") or [])
        suppressed.update(due_stage_types(new))
        meta["expiry_suppressed_types"] = sorted(suppressed)
        log = list(meta.get("expiry_recalculated") or [])[-9:]
        log.append({"from": old.isoformat(), "to": new.isoformat(), "at": datetime.utcnow().isoformat()})
        meta["expiry_recalculated"] = log
        obj.alternatives = meta


_REGISTERED = False


def register() -> None:
    global _REGISTERED
    if not _REGISTERED:
        event.listen(Session, "before_flush", _before_flush)
        _REGISTERED = True
