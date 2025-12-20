from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from ..db_models import NudgeEvents
from ..db import SessionLocal


def log_nudge_event(
    user_id: str,
    warranty_id: str,
    variant: str,
    nudge_type: str,
    acted: bool,
) -> None:
    with SessionLocal() as db:
        event = NudgeEvents(
            user_id=user_id,
            warranty_id=warranty_id,
            variant=variant,
            nudge_type=nudge_type,
            shown_at=datetime.utcnow(),
            acted_at=datetime.utcnow() if acted else None,
            ignored_at=None if acted else datetime.utcnow(),
        )
        db.add(event)
        db.commit()


def fetch_stats(db: Session, user_id: str, warranty_id: str):
    events = db.query(NudgeEvents).filter_by(user_id=user_id, warranty_id=warranty_id).all()
    shown = len(events)
    acted = sum(1 for e in events if e.acted_at)
    ignored = sum(1 for e in events if e.ignored_at and not e.acted_at)
    return shown, acted, ignored
