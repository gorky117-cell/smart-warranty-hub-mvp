from datetime import datetime
from typing import Dict, Optional

from sqlalchemy.orm import Session

from ..models import ReviewItem
from ..storage import generate_id, store
from ..db import SessionLocal
from ..db_models import ReviewDB


def create_review(action: str, payload: Dict) -> ReviewItem:
    item = ReviewItem(
        id=generate_id("rvw"),
        action=action,
        payload=payload,
        status="pending",
        created_at=datetime.utcnow(),
    )
    store.add_review(item)
    with SessionLocal() as db:
        db_item = ReviewDB(
            id=item.id,
            action=item.action,
            payload=item.payload,
            status=item.status,
            created_at=item.created_at,
        )
        db.add(db_item)
        db.commit()
    return item


def approve_review(review_id: str, reason: Optional[str] = None) -> ReviewItem:
    item = store.update_review(review_id, "approved", reason)
    with SessionLocal() as db:
        db_item = db.get(ReviewDB, review_id)
        if db_item:
            db_item.status = "approved"
            db_item.reason = reason
            db_item.resolved_at = datetime.utcnow()
            db.commit()
    return item


def reject_review(review_id: str, reason: Optional[str] = None) -> ReviewItem:
    item = store.update_review(review_id, "rejected", reason)
    with SessionLocal() as db:
        db_item = db.get(ReviewDB, review_id)
        if db_item:
            db_item.status = "rejected"
            db_item.reason = reason
            db_item.resolved_at = datetime.utcnow()
            db.commit()
    return item
