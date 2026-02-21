from __future__ import annotations

from datetime import date, datetime
from typing import Any, Dict, Optional


def _as_date(value: Any) -> Optional[date]:
    if value is None:
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, str):
        raw = value.strip()
        if not raw:
            return None
        try:
            return datetime.fromisoformat(raw).date()
        except ValueError:
            return None
    return None


def _add_months(start: date, months: int) -> date:
    year = start.year + (start.month - 1 + months) // 12
    month = (start.month - 1 + months) % 12 + 1
    day = min(
        start.day,
        [
            31,
            29 if year % 4 == 0 and (year % 100 != 0 or year % 400 == 0) else 28,
            31,
            30,
            31,
            30,
            31,
            31,
            30,
            31,
            30,
            31,
        ][month - 1],
    )
    return date(year, month, day)


def _lapse_text(days_lapsed: int) -> str:
    if days_lapsed < 365:
        months = max(1, round(days_lapsed / 30))
        return f"{months} month(s)"
    years = round(days_lapsed / 365.25, 1)
    return f"{years} year(s)"


def compute_warranty_status(
    *,
    purchase_date: Any,
    coverage_months: Any,
    expiry_date: Any,
    today: Optional[date] = None,
) -> Dict[str, Any]:
    now = today or datetime.utcnow().date()
    purchase = _as_date(purchase_date)
    expiry = _as_date(expiry_date)

    cov: Optional[int] = None
    if coverage_months is not None:
        try:
            cov = int(float(str(coverage_months)))
        except (TypeError, ValueError):
            cov = None

    derived = False
    if not expiry and purchase and cov and cov > 0:
        expiry = _add_months(purchase, cov)
        derived = True

    if not expiry:
        return {
            "status": "unknown",
            "days_left": None,
            "days_lapsed": None,
            "lapsed_text": None,
            "claim_eligibility": "review",
            "claim_message": "Purchase/coverage dates are incomplete. Please verify invoice date to confirm eligibility.",
            "expiry_date_used": None,
            "expiry_source": "none",
        }

    days_left = (expiry - now).days
    if days_left < 0:
        days_lapsed = abs(days_left)
        return {
            "status": "expired",
            "days_left": days_left,
            "days_lapsed": days_lapsed,
            "lapsed_text": _lapse_text(days_lapsed),
            "claim_eligibility": "not_eligible",
            "claim_message": f"Warranty lapsed { _lapse_text(days_lapsed) } ago. Standard claim is typically not eligible.",
            "expiry_date_used": expiry.isoformat(),
            "expiry_source": "derived_from_purchase_plus_coverage" if derived else "provided",
        }

    if days_left < 60:
        status = "expiring_soon"
    else:
        status = "active"

    return {
        "status": status,
        "days_left": days_left,
        "days_lapsed": 0,
        "lapsed_text": None,
        "claim_eligibility": "eligible",
        "claim_message": "Claim is within coverage window.",
        "expiry_date_used": expiry.isoformat(),
        "expiry_source": "derived_from_purchase_plus_coverage" if derived else "provided",
    }
