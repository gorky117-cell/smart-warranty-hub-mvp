import threading
import time
import os
import datetime
from typing import List

from .oem import fetch_oem_page
from .review import create_review
from ..db import SessionLocal
from ..db_models import OEMFetchDB
from .audit import log_action
from .oem_issue_feeds import ingest_oem_issue_feeds
from .risk_refresh import refresh_risk_snapshots
from .data_governance import cleanup_retention
from .review_crawler import crawl_reviews
from .oem_dispatch import run_weekly_dispatch


def oem_refresh_loop(interval_minutes: int = 60):
    last_issue_feed = datetime.datetime.min
    last_risk_refresh = datetime.datetime.min
    last_review_crawl = datetime.datetime.min
    last_cleanup = datetime.datetime.min
    last_oem_analysis = datetime.datetime.min
    last_oem_dispatch = datetime.datetime.min
    issue_interval = int(os.getenv("OEM_ISSUE_FEED_REFRESH_MINUTES", "180"))
    risk_interval = int(os.getenv("RISK_REFRESH_MINUTES", "120"))
    review_interval = int(os.getenv("REVIEW_CRAWL_MINUTES", "1440"))
    review_enabled = os.getenv("REVIEW_CRAWL_ENABLED", "true").lower() == "true"
    cleanup_interval = int(os.getenv("DATA_GOVERNANCE_CLEANUP_MINUTES", "1440"))
    oem_analysis_enabled = os.getenv("OEM_ANALYSIS_ENABLED", "true").lower() == "true"
    oem_analysis_interval = int(os.getenv("OEM_ANALYSIS_MINUTES", "10080"))  # weekly analysis
    oem_dispatch_enabled = os.getenv("OEM_AUTO_DISPATCH_ENABLED", "true").lower() == "true"
    oem_dispatch_interval = int(os.getenv("OEM_AUTO_DISPATCH_MINUTES", "43200"))  # monthly default
    while True:
        try:
            with SessionLocal() as db:
                rows: List[OEMFetchDB] = (
                    db.query(OEMFetchDB).filter(OEMFetchDB.status == "pending").all()
                )
                for row in rows:
                    # Gate through review if required
                    if os.getenv("OEM_REVIEW_REQUIRED", "true").lower() == "true":
                        create_review(
                            "oem_fetch",
                            {
                                "brand": row.brand,
                                "model": row.model,
                                "region": row.region,
                                "url": row.url,
                                "immediate": False,
                            },
                        )
                        row.status = "pending"
                        db.commit()
                        continue
                    try:
                        fetch_oem_page(row.url, row.brand, row.model, row.region)
                        row.status = "fetched"
                        row.updated_at = datetime.datetime.utcnow()
                        db.commit()
                    except Exception as exc:
                        row.status = "failed"
                        row.last_error = str(exc)
                        row.updated_at = datetime.datetime.utcnow()
                        db.commit()
                        log_action("oem_refresh_fail", f"{row.url} err={exc}")
                # Ingest OEM issue feeds on schedule
                now = datetime.datetime.utcnow()
                if issue_interval > 0 and (now - last_issue_feed).total_seconds() >= issue_interval * 60:
                    try:
                        count = ingest_oem_issue_feeds(db)
                        log_action("oem_issue_ingest", f"count={count}")
                    except Exception as exc:
                        log_action("oem_issue_ingest_fail", str(exc))
                    last_issue_feed = now
                # Refresh risk snapshots on schedule
                if risk_interval > 0 and (now - last_risk_refresh).total_seconds() >= risk_interval * 60:
                    try:
                        count = refresh_risk_snapshots(db)
                        log_action("risk_refresh", f"count={count}")
                    except Exception as exc:
                        log_action("risk_refresh_fail", str(exc))
                    last_risk_refresh = now
                # Review crawl on schedule
                if review_enabled and review_interval > 0 and (now - last_review_crawl).total_seconds() >= review_interval * 60:
                    try:
                        stats = crawl_reviews(db, region=os.getenv("REVIEW_REGION", "IN"))
                        log_action("review_crawl", f"pages={stats.get('pages')} reviews={stats.get('reviews')}")
                    except Exception as exc:
                        log_action("review_crawl_fail", str(exc))
                    last_review_crawl = now
                if cleanup_interval > 0 and (now - last_cleanup).total_seconds() >= cleanup_interval * 60:
                    stats = cleanup_retention(db)
                    log_action("governance_cleanup", f"{stats}")
                    last_cleanup = now
                if oem_analysis_enabled and oem_analysis_interval > 0 and (now - last_oem_analysis).total_seconds() >= oem_analysis_interval * 60:
                    try:
                        stats = run_weekly_dispatch(db, dry_run=True)
                        log_action("oem_weekly_analysis", f"{stats}")
                    except Exception as exc:
                        log_action("oem_weekly_analysis_fail", str(exc))
                    last_oem_analysis = now
                if oem_dispatch_enabled and oem_dispatch_interval > 0 and (now - last_oem_dispatch).total_seconds() >= oem_dispatch_interval * 60:
                    try:
                        stats = run_weekly_dispatch(db, dry_run=False)
                        log_action("oem_monthly_dispatch", f"{stats}")
                    except Exception as exc:
                        log_action("oem_monthly_dispatch_fail", str(exc))
                    last_oem_dispatch = now
        except Exception as exc:
            log_action("scheduler_error", str(exc))
        time.sleep(interval_minutes * 60)


def start_scheduler(interval_minutes: int = 240):
    t = threading.Thread(target=oem_refresh_loop, args=(interval_minutes,), daemon=True)
    t.start()
