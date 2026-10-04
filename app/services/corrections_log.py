"""Log what the customer confirmed or corrected, to measure extraction against real invoices.

Off unless CORRECTIONS_LOG=1 (never set in production without the owner's approval). Writes
real_invoices/corrections.csv (git-ignored; override with CORRECTIONS_LOG_PATH). Each row holds only:
time, field name, the value SWH read, the value the customer confirmed or entered, and the action.
No warranty or user ids, names, addresses, phones or invoice text; values pass through the same
redaction as AI calls, so a phone number or e-mail typed into a field is masked.
"""
from __future__ import annotations

import csv
import os
import threading
from datetime import datetime
from pathlib import Path
from typing import Optional

from .privacy import ai_safe

COLUMNS = ["logged_at", "field", "value_read", "value_confirmed", "action"]
LOGGED_FIELDS = {"brand", "model_code", "serial_no", "product_name", "purchase_date", "invoice_no"}
_LOCK = threading.Lock()
_DEFAULT_PATH = Path(__file__).resolve().parents[2] / "real_invoices" / "corrections.csv"


def enabled() -> bool:
    return (os.getenv("CORRECTIONS_LOG") or "").strip().lower() in ("1", "true", "yes", "on")


def _path() -> Path:
    return Path(os.getenv("CORRECTIONS_LOG_PATH") or _DEFAULT_PATH)


def _clean(value: Optional[object]) -> str:
    text = " ".join(str(value or "").split())[:80]
    return ai_safe(text) if text else ""


def log_correction(field: str, value_read: Optional[object], value_confirmed: Optional[object], action: str) -> bool:
    """Append one row; returns True when written. Never raises into the request."""
    if not enabled() or field not in LOGGED_FIELDS:
        return False
    read, confirmed = _clean(value_read), _clean(value_confirmed)
    if action == "confirm":
        action = "confirmed" if read.upper() == confirmed.upper() else "corrected"
    try:
        path = _path()
        path.parent.mkdir(parents=True, exist_ok=True)
        with _LOCK:
            new_file = not path.exists()
            with path.open("a", encoding="utf-8", newline="") as fh:
                writer = csv.writer(fh)
                if new_file:
                    writer.writerow(COLUMNS)
                writer.writerow([datetime.utcnow().isoformat(timespec="seconds"), field, read, confirmed, action])
        return True
    except Exception:
        return False
