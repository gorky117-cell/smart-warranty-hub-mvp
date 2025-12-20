from datetime import datetime, timedelta
from typing import Optional, Tuple

from sqlalchemy.orm import Session

from ..db_models import BehaviourAnswer, BehaviourProfile, BehaviourQuestion, WarrantyDB
from ..db import SessionLocal


COOLDOWN_DAYS = 7


def _infer_product_type(db: Session, product_type: Optional[str], warranty_id: Optional[str]) -> Optional[str]:
    if product_type:
        return product_type
    if warranty_id:
        w = db.query(WarrantyDB).filter_by(id=warranty_id).first()
        if w and w.product_name:
            name = (w.product_name or "").lower()
            if "fridge" in name:
                return "fridge"
            if "ac" in name or "air" in name:
                return "ac"
            if "wash" in name:
                return "washer"
        if w and w.model_code:
            return w.model_code
    return None


def _get_profile(db: Session, user_id: str, product_type: Optional[str], warranty_id: Optional[str]) -> BehaviourProfile:
    profile = (
        db.query(BehaviourProfile)
        .filter_by(user_id=user_id, product_type=product_type, warranty_id=warranty_id)
        .first()
    )
    if not profile:
        profile = BehaviourProfile(
            user_id=user_id,
            product_type=product_type,
            warranty_id=warranty_id,
            behaviour_score=0.5,
            care_score=0.5,
            responsiveness_score=0.5,
        )
        db.add(profile)
        db.commit()
        db.refresh(profile)
    return profile


def get_next_question(
    user_id: str,
    product_type: Optional[str],
    warranty_id: Optional[str],
    brand: Optional[str],
    model_code: Optional[str],
) -> Optional[BehaviourQuestion]:
    with SessionLocal() as db:
        pt = _infer_product_type(db, product_type, warranty_id)
        profile = _get_profile(db, user_id, pt, warranty_id)
        if profile.last_question_at and profile.last_question_at > datetime.utcnow() - timedelta(days=COOLDOWN_DAYS):
            return None
        answered_ids = {
            q.question_id
            for q in db.query(BehaviourAnswer).filter_by(user_id=user_id, product_type=pt).all()
        }
        candidates = (
            db.query(BehaviourQuestion)
            .filter(BehaviourQuestion.is_active == 1)
            .filter(
                (BehaviourQuestion.brand == brand) | (BehaviourQuestion.brand.is_(None)),
                (BehaviourQuestion.model_code == model_code) | (BehaviourQuestion.model_code.is_(None)),
                (BehaviourQuestion.product_type == pt) | (BehaviourQuestion.product_type.is_(None)),
            )
            .order_by(BehaviourQuestion.weight.desc(), BehaviourQuestion.id.asc())
            .all()
        )
        for q in candidates:
            if q.id not in answered_ids:
                profile.last_question_at = datetime.utcnow()
                db.commit()
                return q
        return None


def _apply_scoring(profile: BehaviourProfile, answer_value: str) -> None:
    def clamp(val: float) -> float:
        return max(0.0, min(1.0, val))

    val_lower = (answer_value or "").lower()
    if val_lower in ("yes", "y", "true", "1", "5"):
        profile.care_score = clamp(profile.care_score + 0.03)
        profile.behaviour_score = clamp(profile.behaviour_score + 0.01)
    elif val_lower in ("no", "n", "false", "0"):
        profile.behaviour_score = clamp(profile.behaviour_score - 0.02)
    if val_lower in ("1", "2"):
        profile.behaviour_score = clamp(profile.behaviour_score - 0.05)
    if val_lower in ("4", "5"):
        profile.responsiveness_score = clamp(profile.responsiveness_score + 0.02)
    profile.responsiveness_score = clamp(profile.responsiveness_score + 0.02)


def record_answer(
    user_id: str,
    product_type: Optional[str],
    warranty_id: Optional[str],
    question_id: int,
    answer_value: str,
) -> BehaviourProfile:
    with SessionLocal() as db:
        pt = _infer_product_type(db, product_type, warranty_id)
        answer = BehaviourAnswer(
            user_id=user_id,
            product_type=pt,
            warranty_id=warranty_id,
            question_id=question_id,
            answer_value=answer_value,
            created_at=datetime.utcnow(),
        )
        db.add(answer)
        profile = _get_profile(db, user_id, pt, warranty_id)
        _apply_scoring(profile, answer_value)
        profile.last_question_at = datetime.utcnow()
        profile.last_updated_at = datetime.utcnow()
        db.commit()
        db.refresh(profile)
        return profile


def get_profile(db: Session, user_id: str, product_type: Optional[str], warranty_id: Optional[str]) -> BehaviourProfile:
    return _get_profile(db, user_id, product_type, warranty_id)


def get_profile_safe(user_id: str, product_type: Optional[str], warranty_id: Optional[str]) -> Tuple[float, float, float]:
    try:
        with SessionLocal() as db:
            profile = _get_profile(db, user_id, _infer_product_type(db, product_type, warranty_id), warranty_id)
            return profile.behaviour_score, profile.care_score, profile.responsiveness_score
    except Exception:
        return 0.5, 0.5, 0.5
