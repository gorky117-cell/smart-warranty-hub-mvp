from __future__ import annotations

import os
from datetime import datetime, timedelta
from typing import Dict

from sqlalchemy.orm import Session

from ..db_models import ProductReviewDB, ReviewPageDB, SymptomSearch, TelemetryEventDB
from .audit import log_action


def cleanup_retention(db: Session) -> Dict[str, int]:
    """
    Delete old data based on retention env vars.
    """
    now = datetime.utcnow()
    review_days = int(os.getenv("REVIEW_RETENTION_DAYS", "365"))
    review_page_days = int(os.getenv("REVIEW_PAGE_RETENTION_DAYS", "90"))
    telemetry_days = int(os.getenv("TELEMETRY_RETENTION_DAYS", "365"))
    search_days = int(os.getenv("SEARCH_LOG_RETENTION_DAYS", "365"))

    stats = {"reviews": 0, "review_pages": 0, "telemetry": 0, "search_logs": 0}
    try:
        if review_days > 0:
            cutoff = now - timedelta(days=review_days)
            stats["reviews"] = db.query(ProductReviewDB).filter(ProductReviewDB.created_at < cutoff).delete()
        if review_page_days > 0:
            cutoff = now - timedelta(days=review_page_days)
            stats["review_pages"] = db.query(ReviewPageDB).filter(ReviewPageDB.fetched_at < cutoff).delete()
        if telemetry_days > 0:
            cutoff = now - timedelta(days=telemetry_days)
            stats["telemetry"] = db.query(TelemetryEventDB).filter(TelemetryEventDB.timestamp < cutoff).delete()
        if search_days > 0:
            cutoff = now - timedelta(days=search_days)
            stats["search_logs"] = db.query(SymptomSearch).filter(SymptomSearch.created_at < cutoff).delete()
        db.commit()
    except Exception as exc:
        log_action("governance_cleanup_fail", str(exc))
        db.rollback()
    return stats
