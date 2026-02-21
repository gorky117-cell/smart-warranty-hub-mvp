import uuid

from app.db import SessionLocal
from app.db_models import PolicyAssignmentDB
from app.services.policy import assign_variant
from app.storage import store


def _reset_policy_assignments() -> None:
    with SessionLocal() as db:
        db.query(PolicyAssignmentDB).delete()
        db.commit()
    store.policy_assignments.clear()


def test_assign_variant_idempotent_single_row():
    _reset_policy_assignments()
    experiment = f"fogg_ab_idem_{uuid.uuid4().hex[:8]}"
    user_id = "policy_user_1"
    warranty_id = "policy_warranty_1"

    v1 = assign_variant(user_id, warranty_id, experiment=experiment, variants=("A", "B"))
    v2 = assign_variant(user_id, warranty_id, experiment=experiment, variants=("A", "B"))

    assert v1 == v2
    with SessionLocal() as db:
        rows = (
            db.query(PolicyAssignmentDB)
            .filter(
                PolicyAssignmentDB.experiment == experiment,
                PolicyAssignmentDB.user_id == user_id,
                PolicyAssignmentDB.warranty_id == warranty_id,
            )
            .all()
        )
    assert len(rows) == 1


def test_assign_variant_balances_ab_split_within_one():
    _reset_policy_assignments()
    experiment = f"fogg_ab_balance_{uuid.uuid4().hex[:8]}"
    counts = {"A": 0, "B": 0}
    total = 50

    for i in range(total):
        variant = assign_variant(
            user_id=f"policy_user_{i}",
            warranty_id=f"policy_warranty_{i}",
            experiment=experiment,
            variants=("A", "B"),
        )
        assert variant in ("A", "B")
        counts[variant] += 1

    assert abs(counts["A"] - counts["B"]) <= 1
    with SessionLocal() as db:
        row_count = db.query(PolicyAssignmentDB).filter(PolicyAssignmentDB.experiment == experiment).count()
    assert row_count == total
