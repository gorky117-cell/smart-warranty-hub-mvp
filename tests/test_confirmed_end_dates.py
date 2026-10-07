"""Owner review of PR #3, item 2 (backlog #24): reminders, notifications and the claim PDF use only CONFIRMED end
dates - from the brand's terms, or stated on the warranty card / invoice (or given by the customer). Estimated or
unknown -> "Check your warranty card" and no expiry reminder."""
from datetime import date, datetime, timedelta

import pytest

from app.db import SessionLocal
from app.db_models import CareGuideDB, NotificationDB, UserDB, WarrantyDB, WarrantyOwnerDB
from app.deps import hash_password
from app.services import customer_content, notifications, summary_engine, warranty_card
from app.services.reminders import refresh_care_reminders

USER = "confirmed_end_user"
SOON = datetime.utcnow() + timedelta(days=5)

KB = {"terms_source_type": "knowledge_base", "terms_source_url": "https://www.lg.com/in/support/warranty"}
ESTIMATE = {"terms_source_type": "default_rules", "terms_source_url": "internal://default_rules"}

# (name, alternatives, confidence, confirmed?)
CASES = [
    ("brand terms (knowledge base)", KB, {}, True),
    ("printed on the invoice", ESTIMATE, {"coverage_months": 0.7}, True),
    ("given by the customer", ESTIMATE, {"coverage_months": 0.95}, True),
    ("estimated (typical terms)", ESTIMATE, {}, False),
    ("unknown source", {}, {}, False),
]


def _seed(wid, alternatives, confidence, *, purchase=datetime(2025, 11, 1), months=12, expiry=SOON, product="LG Double Door Refrigerator"):
    with SessionLocal() as db:
        if not db.query(UserDB).filter_by(username=USER).first():
            db.add(UserDB(username=USER, role="user", hashed_password=hash_password("secret123"), email="c@example.com"))
        db.query(NotificationDB).filter_by(warranty_id=wid).delete()
        db.query(WarrantyOwnerDB).filter_by(warranty_id=wid).delete()
        db.query(WarrantyDB).filter_by(id=wid).delete()
        db.add(WarrantyDB(id=wid, brand="LG", product_name=product, model_code="GL-T292RPZY", purchase_date=purchase,
                          coverage_months=months, expiry_date=expiry, alternatives=dict(alternatives),
                          confidence=dict(confidence), terms=["Standard coverage for 12 months from purchase date.",
                                                              "Manufacturing defects covered under normal usage."]))
        db.add(WarrantyOwnerDB(user_id=USER, warranty_id=wid))
        db.commit()


def _row(wid):
    with SessionLocal() as db:
        row = db.query(WarrantyDB).filter_by(id=wid).first()
        db.expunge(row)
        return row


@pytest.mark.parametrize("name,alts,conf,confirmed", CASES)
def test_confirmed_end_date(name, alts, conf, confirmed):
    _seed("ced_1", alts, conf)
    end = warranty_card.confirmed_end_date(_row("ced_1"))
    assert (end == SOON.date()) if confirmed else (end is None), name


def test_no_purchase_or_end_date_is_unknown():
    _seed("ced_2", KB, {}, purchase=None, expiry=None)
    assert warranty_card.confirmed_end_date(_row("ced_2")) is None


@pytest.mark.parametrize("name,alts,conf,confirmed", CASES)
def test_expiry_reminders_only_for_confirmed_dates(name, alts, conf, confirmed):
    _seed("ced_3", alts, conf)
    with SessionLocal() as db:
        created = notifications.create_expiry_notifications(db=db, user_id=USER, warranty_id="ced_3")
        notifications.refresh_expiry_notifications(db)
        types = [n.type for n in db.query(NotificationDB).filter_by(warranty_id="ced_3").all()]
    if confirmed:
        assert [n["type"] for n in created] == ["expiry_7d"] and types == ["expiry_7d"], name
    else:
        assert created == [] and types == [], name


def test_expired_by_estimate_sends_no_ended_notice():
    _seed("ced_4", ESTIMATE, {}, purchase=datetime(2015, 1, 1), expiry=datetime(2016, 1, 1))
    with SessionLocal() as db:
        notifications.refresh_expiry_notifications(db)
        assert db.query(NotificationDB).filter_by(warranty_id="ced_4").count() == 0


def test_care_reminders_do_not_use_estimated_dates(monkeypatch):
    # A care guide with an interval exists for this product; with only an estimated end date the product's status
    # is unknown, so no care reminder is scheduled from that estimate.
    from app.services import care_guides, reuse_policy

    _seed("ced_5", ESTIMATE, {})
    monkeypatch.setattr(care_guides, "find", lambda db, **kw: [CareGuideDB(company="LG", tips=[{"quote": "Clean every 30 days."}])])
    monkeypatch.setattr(reuse_policy, "allows", lambda *a, **k: True)
    with SessionLocal() as db:
        db.add(CareGuideDB(company="LG", product_scope="line:fridge", source_kind="faq", checked_by="admin",
                           source_url="https://www.lg.com/in/ced-test",
                           tips=[{"text": "Clean the gasket.", "quote": "Clean every 30 days."}]))
        db.commit()
        stats = refresh_care_reminders(db)
        db.query(CareGuideDB).filter_by(source_url="https://www.lg.com/in/ced-test").delete()
        db.commit()
        assert db.query(NotificationDB).filter(NotificationDB.warranty_id == "ced_5",
                                               NotificationDB.type.like("care_%")).count() == 0
    assert stats["expired_or_unknown"] >= 1


@pytest.mark.parametrize("name,alts,conf,confirmed", CASES)
def test_claim_pdf_text(name, alts, conf, confirmed):
    _seed("ced_6", alts, conf)
    row = _row("ced_6")
    text = customer_content.export_text(row, summary_engine.build_evidence_summary(row))
    if confirmed:
        assert f"Expiry: {SOON.date().isoformat()}" in text, name
    else:
        assert "Expiry: check your warranty card" in text and "Coverage: check your warranty card" in text, name
        assert "Check your warranty card for how long the warranty lasts" in text
        assert "12 months" not in text  # the estimated "Standard coverage for 12 months" line is left out
        assert "Manufacturing defects covered under normal usage." in text
