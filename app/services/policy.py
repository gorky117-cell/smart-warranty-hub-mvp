import hashlib
from typing import Iterable

from sqlalchemy import select, func

from ..storage import store
from ..db import SessionLocal
from ..db_models import PolicyAssignmentDB


def _stable_index(key: str, modulo: int) -> int:
    if modulo <= 1:
        return 0
    digest = hashlib.sha256(key.encode("utf-8")).hexdigest()
    return int(digest[:16], 16) % modulo


def _choose_variant_balanced(db, *, experiment: str, user_id: str, warranty_id: str, var_list: list[str]) -> str:
    # For 2-variant experiments, keep global counts near 50/50.
    if len(var_list) == 2:
        rows = (
            db.query(PolicyAssignmentDB.variant, func.count(PolicyAssignmentDB.id))
            .filter(
                PolicyAssignmentDB.experiment == experiment,
                PolicyAssignmentDB.variant.in_(var_list),
            )
            .group_by(PolicyAssignmentDB.variant)
            .all()
        )
        counts = {v: int(c) for v, c in rows}
        v0, v1 = var_list
        c0 = counts.get(v0, 0)
        c1 = counts.get(v1, 0)
        if c0 < c1:
            return v0
        if c1 < c0:
            return v1
        # tie-breaker is stable per user+warranty key
        idx = _stable_index(f"{experiment}:{user_id}:{warranty_id}", 2)
        return var_list[idx]
    # For >2 variants, use stable hash bucketing.
    idx = _stable_index(f"{experiment}:{user_id}:{warranty_id}", len(var_list))
    return var_list[idx]


def assign_variant(user_id: str, warranty_id: str, experiment: str = "fogg_nudge", variants: Iterable[str] = ("A", "B")) -> str:
    existing = store.get_policy_variant(experiment, user_id, warranty_id)
    if existing:
        return existing
    var_list = [str(v).strip() for v in variants if str(v).strip()]
    if not var_list:
        var_list = ["A", "B"]
    if len(var_list) == 1:
        choice = var_list[0]
        store.set_policy_variant(experiment, user_id, warranty_id, choice)
        return choice
    with SessionLocal() as db:
        stmt = select(PolicyAssignmentDB).where(
            PolicyAssignmentDB.experiment == experiment,
            PolicyAssignmentDB.user_id == user_id,
            PolicyAssignmentDB.warranty_id == warranty_id,
        )
        res = db.execute(stmt).scalars().first()
        if res:
            store.policy_assignments[f"{experiment}:{user_id}:{warranty_id}"] = res.variant
            return res.variant
        choice = _choose_variant_balanced(
            db,
            experiment=experiment,
            user_id=user_id,
            warranty_id=warranty_id,
            var_list=var_list,
        )
        db.add(
            PolicyAssignmentDB(
                experiment=experiment, user_id=user_id, warranty_id=warranty_id, variant=choice
            )
        )
        db.commit()
    # Cache assignment in memory after DB commit.
    store.policy_assignments[f"{experiment}:{user_id}:{warranty_id}"] = choice
    return choice


def get_variant(user_id: str, warranty_id: str, experiment: str = "fogg_nudge") -> str | None:
    return store.get_policy_variant(experiment, user_id, warranty_id)
