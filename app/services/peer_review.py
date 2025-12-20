from collections import Counter, defaultdict
from datetime import datetime
from typing import Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from ..db import SessionLocal
from ..db_models import PeerReviewSignals


def record_peer_signal(
    db: Session,
    product_type: Optional[str],
    brand: Optional[str],
    model: Optional[str],
    symptom_keyword: Optional[str],
    severity_hint: Optional[str],
    source: Optional[str],
    avg_rating: Optional[float] = None,
    review_sentiment: Optional[float] = None,
    warranty_id: Optional[str] = None,
    failure_keywords: Optional[List[str]] = None,
) -> PeerReviewSignals:
    rec = (
        db.query(PeerReviewSignals)
        .filter_by(warranty_id=warranty_id or None, brand=brand or None, model=model or None)
        .order_by(PeerReviewSignals.last_updated_at.desc())
        .first()
    )
    if not rec:
        rec = PeerReviewSignals(
            warranty_id=warranty_id,
            product_type=product_type,
            brand=brand,
            model=model,
            avg_rating=avg_rating,
            review_sentiment=review_sentiment,
            failure_keywords=failure_keywords or [],
            symptom_keyword=symptom_keyword,
            severity_hint=severity_hint,
            source=source,
            last_updated_at=datetime.utcnow(),
        )
        db.add(rec)
    else:
        rec.product_type = product_type or rec.product_type
        rec.avg_rating = avg_rating if avg_rating is not None else rec.avg_rating
        rec.review_sentiment = review_sentiment if review_sentiment is not None else rec.review_sentiment
        rec.failure_keywords = failure_keywords or rec.failure_keywords
        rec.symptom_keyword = symptom_keyword or rec.symptom_keyword
        rec.severity_hint = severity_hint or rec.severity_hint
        rec.source = source or rec.source
        rec.last_updated_at = datetime.utcnow()
    db.commit()
    db.refresh(rec)
    return rec


def get_issue_stats(
    product_type: Optional[str],
    brand: Optional[str],
    model: Optional[str],
    region: Optional[str] = None,  # region kept for forward compatibility
) -> Dict[str, object]:
    try:
        with SessionLocal() as db:
            query = db.query(PeerReviewSignals)
            if product_type:
                query = query.filter_by(product_type=product_type)
            if brand:
                query = query.filter_by(brand=brand)
            if model:
                query = query.filter_by(model=model)
            rows = query.all()
    except Exception:
        # Handle older SQLite files that may miss newer columns
        return {
            "count": 0,
            "severity": {},
            "top_keywords": [],
            "avg_rating": None,
            "avg_sentiment": None,
        }

    severity_counter: Counter = Counter()
    keyword_counter: Counter = Counter()
    for row in rows:
        if row.severity_hint:
            severity_counter[row.severity_hint] += 1
        if row.symptom_keyword:
            keyword_counter[row.symptom_keyword] += 1
        for kw in row.failure_keywords or []:
            keyword_counter[kw] += 1

    return {
        "count": len(rows),
        "severity": dict(severity_counter),
        "top_keywords": [kw for kw, _ in keyword_counter.most_common(5)],
        "avg_rating": float(sum(r.avg_rating or 0.0 for r in rows) / len(rows)) if rows else None,
        "avg_sentiment": float(sum(r.review_sentiment or 0.0 for r in rows) / len(rows)) if rows else None,
    }


def upsert_peer_review(db: Session, brand: str, model: str, warranty_id: str, avg_rating: float, review_sentiment: float, failure_keywords: List[str]):
    # Backward compatible helper
    return record_peer_signal(
        db=db,
        product_type=None,
        brand=brand,
        model=model,
        symptom_keyword=None,
        severity_hint=None,
        source=None,
        avg_rating=avg_rating,
        review_sentiment=review_sentiment,
        warranty_id=warranty_id,
        failure_keywords=failure_keywords,
    )


def get_peer_review(db: Session, warranty_id: str, brand: Optional[str], model: Optional[str]) -> Optional[PeerReviewSignals]:
    rec = db.query(PeerReviewSignals).filter_by(warranty_id=warranty_id).first()
    if rec:
        return rec
    if brand and model:
        rec = (
            db.query(PeerReviewSignals)
            .filter_by(brand=brand, model=model)
            .order_by(PeerReviewSignals.last_updated_at.desc())
            .first()
        )
        return rec
    return None
