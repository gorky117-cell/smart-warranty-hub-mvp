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
from . import notifications as notification_service
from .data_governance import cleanup_retention
from .review_crawler import crawl_reviews
from .oem_dispatch import run_weekly_dispatch
from .kpi_watchdog import run_kpi_watchdog
from .kpi_remediation import run_kpi_remediation_cycle
from .kpi_execution import run_execution_cycle
from . import remote_diagnostics as remote_diag_service


def oem_refresh_loop(interval_minutes: int = 60):
    last_issue_feed = datetime.datetime.min
    last_risk_refresh = datetime.datetime.min
    last_review_crawl = datetime.datetime.min
    last_cleanup = datetime.datetime.min
    last_expiry_refresh = datetime.datetime.min
    last_oem_analysis = datetime.datetime.min
    last_oem_dispatch = datetime.datetime.min
    last_kpi_watchdog = datetime.datetime.min
    last_kpi_remediation = datetime.datetime.min
    last_kpi_execution = datetime.datetime.min
    last_remote_diag_run = datetime.datetime.min
    issue_interval = int(os.getenv("OEM_ISSUE_FEED_REFRESH_MINUTES", "180"))
    risk_interval = int(os.getenv("RISK_REFRESH_MINUTES", "120"))
    review_interval = int(os.getenv("REVIEW_CRAWL_MINUTES", "1440"))
    review_enabled = os.getenv("REVIEW_CRAWL_ENABLED", "true").lower() == "true"
    cleanup_interval = int(os.getenv("DATA_GOVERNANCE_CLEANUP_MINUTES", "1440"))
    expiry_interval = int(os.getenv("EXPIRY_REMINDER_MINUTES", "720"))
    expiry_enabled = os.getenv("EXPIRY_REMINDER_ENABLED", "true").lower() == "true"
    oem_analysis_enabled = os.getenv("OEM_ANALYSIS_ENABLED", "true").lower() == "true"
    oem_analysis_interval = int(os.getenv("OEM_ANALYSIS_MINUTES", "10080"))  # weekly analysis
    oem_dispatch_enabled = os.getenv("OEM_AUTO_DISPATCH_ENABLED", "true").lower() == "true"
    oem_dispatch_interval = int(os.getenv("OEM_AUTO_DISPATCH_MINUTES", "43200"))  # monthly default
    kpi_watchdog_enabled = os.getenv("KPI_WATCHDOG_ENABLED", "true").lower() == "true"
    kpi_watchdog_interval = int(os.getenv("KPI_WATCHDOG_MINUTES", "1440"))  # daily default
    kpi_remediation_enabled = os.getenv("KPI_REMEDIATION_ENABLED", "true").lower() == "true"
    kpi_remediation_interval = int(os.getenv("KPI_REMEDIATION_MINUTES", "1440"))  # daily default
    kpi_execution_enabled = os.getenv("KPI_EXECUTION_ENABLED", "true").lower() == "true"
    kpi_execution_interval = int(os.getenv("KPI_EXECUTION_MINUTES", "720"))  # 12h default
    remote_diag_enabled = os.getenv("REMOTE_DIAGNOSTICS_AUTO_EXECUTE", "true").lower() == "true"
    remote_diag_interval = int(os.getenv("REMOTE_DIAGNOSTICS_POLL_MINUTES", "5"))
    remote_diag_batch = int(os.getenv("REMOTE_DIAGNOSTICS_BATCH_SIZE", "10"))
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
                if expiry_enabled and expiry_interval > 0 and (now - last_expiry_refresh).total_seconds() >= expiry_interval * 60:
                    try:
                        stats = notification_service.refresh_expiry_notifications(db)
                        log_action("expiry_reminder_refresh", f"{stats}")
                    except Exception as exc:
                        log_action("expiry_reminder_refresh_fail", str(exc))
                    last_expiry_refresh = now
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
                if kpi_watchdog_enabled and kpi_watchdog_interval > 0 and (now - last_kpi_watchdog).total_seconds() >= kpi_watchdog_interval * 60:
                    try:
                        stats = run_kpi_watchdog(db, notify=True)
                        log_action("kpi_watchdog", f"{stats}")
                    except Exception as exc:
                        log_action("kpi_watchdog_fail", str(exc))
                    last_kpi_watchdog = now
                if kpi_remediation_enabled and kpi_remediation_interval > 0 and (now - last_kpi_remediation).total_seconds() >= kpi_remediation_interval * 60:
                    try:
                        stats = run_kpi_remediation_cycle(db, notify=True, source="scheduler")
                        log_action("kpi_remediation", f"{stats}")
                    except Exception as exc:
                        log_action("kpi_remediation_fail", str(exc))
                    last_kpi_remediation = now
                if kpi_execution_enabled and kpi_execution_interval > 0 and (now - last_kpi_execution).total_seconds() >= kpi_execution_interval * 60:
                    try:
                        stats = run_execution_cycle(db, notify=True, source="scheduler")
                        log_action("kpi_execution", f"{stats}")
                    except Exception as exc:
                        log_action("kpi_execution_fail", str(exc))
                    last_kpi_execution = now
                if remote_diag_enabled and remote_diag_interval > 0 and (now - last_remote_diag_run).total_seconds() >= remote_diag_interval * 60:
                    try:
                        stats = remote_diag_service.run_pending_commands(
                            db,
                            limit=max(1, remote_diag_batch),
                            executor="scheduler",
                        )
                        log_action("remote_diagnostics_run", f"{stats}")
                    except Exception as exc:
                        log_action("remote_diagnostics_run_fail", str(exc))
                    last_remote_diag_run = now
        except Exception as exc:
            log_action("scheduler_error", str(exc))
        time.sleep(interval_minutes * 60)


def start_scheduler(interval_minutes: int = 240):
    if os.getenv("SCHEDULER_ENABLED", "true").strip().lower() not in ("1", "true", "yes"):
        log_action("scheduler_disabled", "SCHEDULER_ENABLED=false")
        return
    t = threading.Thread(target=oem_refresh_loop, args=(interval_minutes,), daemon=True)
    t.start()
