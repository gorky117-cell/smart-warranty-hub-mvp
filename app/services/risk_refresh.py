from __future__ import annotations

from typing import List, Tuple

from sqlalchemy.orm import Session

from ..db_models import BehaviourProfile, RiskSnapshotDB
from .predictive import score_warranty
from . import notifications as notification_service


def _distinct_pairs(db: Session) -> List[Tuple[str, str]]:
    pairs = (
        db.query(BehaviourProfile.user_id, BehaviourProfile.warranty_id)
        .distinct()
        .all()
    )
    return [(u, w) for u, w in pairs if u and w]


def refresh_risk_snapshots(db: Session) -> int:
    """
    Re-score warranties for known user+warranty pairs and notify on label change.
    """
    count = 0
    pairs = _distinct_pairs(db)
    for user_id, warranty_id in pairs:
        result = score_warranty(user_id, warranty_id)
        label = result.get("risk_label", "LOW")
        score = float(result.get("risk_score", 0.0))
        last = (
            db.query(RiskSnapshotDB)
            .filter_by(user_id=user_id, warranty_id=warranty_id)
            .order_by(RiskSnapshotDB.created_at.desc())
            .first()
        )
        if not last or last.risk_label != label:
            severity = "critical" if label == "HIGH" else "warning" if label == "MEDIUM" else "info"
            notification_service.create_notification(
                db=db,
                user_id=user_id,
                warranty_id=warranty_id,
                type=f"risk_{label.lower()}",
                title=f"Risk {label.title()} detected",
                message=f"Predictive model flagged {label.lower()} risk for warranty {warranty_id}.",
                severity=severity,
            )
        snap = RiskSnapshotDB(
            user_id=user_id,
            warranty_id=warranty_id,
            risk_label=label,
            risk_score=score,
        )
        db.add(snap)
        db.commit()
        count += 1
    return count
