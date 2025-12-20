import asyncio
import datetime
import os
from typing import List

from .oem import fetch_oem_page
from .review import create_review
from ..db import SessionLocal
from ..db_models import OEMFetchDB
from .audit import log_action


async def oem_refresh_loop(interval_minutes: int = 60):
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
        except Exception as exc:
            log_action("scheduler_error", str(exc))
        await asyncio.sleep(interval_minutes * 60)


def start_scheduler(interval_minutes: int = 60):
    loop = asyncio.get_event_loop()
    loop.create_task(oem_refresh_loop(interval_minutes))
