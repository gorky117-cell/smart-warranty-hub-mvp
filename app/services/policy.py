import random
from typing import Iterable, Tuple

from sqlalchemy import select

from ..storage import store
from ..db import SessionLocal
from ..db_models import PolicyAssignmentDB


def assign_variant(user_id: str, warranty_id: str, experiment: str = "fogg_nudge", variants: Iterable[str] = ("A", "B")) -> str:
    existing = store.get_policy_variant(experiment, user_id, warranty_id)
    if existing:
        return existing
    with SessionLocal() as db:
        stmt = select(PolicyAssignmentDB).where(
            PolicyAssignmentDB.experiment == experiment,
            PolicyAssignmentDB.user_id == user_id,
            PolicyAssignmentDB.warranty_id == warranty_id,
        )
        res = db.execute(stmt).scalars().first()
        if res:
            store.set_policy_variant(experiment, user_id, warranty_id, res.variant)
            return res.variant
    var_list = list(variants)
    choice = random.choice(var_list)
    store.set_policy_variant(experiment, user_id, warranty_id, choice)
    with SessionLocal() as db:
        db.add(
            PolicyAssignmentDB(
                experiment=experiment, user_id=user_id, warranty_id=warranty_id, variant=choice
            )
        )
        db.commit()
    return choice


def get_variant(user_id: str, warranty_id: str, experiment: str = "fogg_nudge") -> str | None:
    return store.get_policy_variant(experiment, user_id, warranty_id)
