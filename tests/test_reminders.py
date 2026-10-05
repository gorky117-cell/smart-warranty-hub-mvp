"""Run 3 item 10: expiry reminders (30 and 7 days, one 'ended' notice), care reminders, frequency limits."""

from datetime import date, datetime, timedelta

import pytest

from app.db import SessionLocal
from app.db_models import CareGuideDB, NotificationDB, UserDB, WarrantyDB, WarrantyOwnerDB
from app.deps import hash_password
from app.services import notifications as ns
from app.services.reminders import interval_days, refresh_care_reminders

USER = "remind_user"
TODAY = date.today()


def _add(db, wid, *, brand, name, model, days_left, months=12):
    expiry = TODAY + timedelta(days=days_left)
    db.add(WarrantyDB(id=wid, brand=brand, product_name=name, model_code=model, purchase_date=datetime(2024, 1, 1),
                      coverage_months=months, expiry_date=datetime.combine(expiry, datetime.min.time()), alternatives={}))
    db.add(WarrantyOwnerDB(user_id=USER, warranty_id=wid))


@pytest.fixture(autouse=True)
def _reset(monkeypatch):
    monkeypatch.setenv("EXPIRY_REMINDER_STAGE_DAYS", "30,7,0")
    monkeypatch.delenv("REMINDER_MAX_PER_DAY", raising=False)
    with SessionLocal() as db:
        db.query(NotificationDB).filter_by(user_id=USER).delete()
        db.query(WarrantyOwnerDB).filter_by(user_id=USER).delete()
        db.query(WarrantyDB).filter(WarrantyDB.id.like("wty_rem_%")).delete(synchronize_session=False)
        db.query(CareGuideDB).filter(CareGuideDB.source_url.like("https://www.%/remind-test%")).delete(synchronize_session=False)
        if not db.query(UserDB).filter_by(username=USER).first():
            db.add(UserDB(username=USER, role="user", hashed_password=hash_password("secret123")))
        db.commit()


def _types(db, wid=None):
    q = db.query(NotificationDB).filter_by(user_id=USER)
    if wid:
        q = q.filter_by(warranty_id=wid)
    return sorted(n.type for n in q.all())


@pytest.mark.parametrize("days_left,expected", [
    (25, ["expiry_30d"]), (5, ["expiry_7d"]), (0, ["expiry_due"]), (-400, ["expiry_expired"]), (90, []),
])
def test_expiry_stage_for_each_window(days_left, expected):
    with SessionLocal() as db:
        _add(db, "wty_rem_1", brand="LG", name="LG Double Door Refrigerator", model="GL-T292RPZY", days_left=days_left)
        db.commit()
        ns.refresh_expiry_notifications(db)
        ns.refresh_expiry_notifications(db)  # repeated runs never repeat a stage
        assert _types(db, "wty_rem_1") == expected


def test_reminder_text_names_the_product_and_date():
    with SessionLocal() as db:
        _add(db, "wty_rem_2", brand="Samsung", name="Samsung Galaxy M17e 5G (Blue, 6GB RAM)", model="SM-M175F", days_left=25)
        db.commit()
        ns.refresh_expiry_notifications(db)
        n = db.query(NotificationDB).filter_by(user_id=USER, warranty_id="wty_rem_2").one()
    expiry = TODAY + timedelta(days=25)
    assert n.title == "Warranty ends in 25 days: Samsung Galaxy M17e 5G"
    assert f"ends on {expiry.day} {expiry.strftime('%b %Y')}" in n.message and "wty_" not in n.message


def test_expired_warranty_gets_one_notice_and_nothing_else():
    with SessionLocal() as db:
        _add(db, "wty_rem_3", brand="Xiaomi", name="Redmi 13C", model="13C", days_left=-200)
        db.add(CareGuideDB(company="Xiaomi", product_scope="model:13C", source_kind="manual",
                           source_url="https://www.mi.com/remind-test", checked_by="admin",
                           tips=[{"text": "Restart the phone once a week.", "quote": "Restart the phone once a week.", "page": ""}]))
        db.commit()
        for _ in range(3):
            ns.refresh_expiry_notifications(db)
            refresh_care_reminders(db)
        assert _types(db, "wty_rem_3") == ["expiry_expired"]
        n = db.query(NotificationDB).filter_by(user_id=USER, warranty_id="wty_rem_3").one()
        assert n.title == "Warranty ended: Xiaomi Redmi 13C"


def test_daily_cap_spreads_reminders_without_losing_them(monkeypatch):
    monkeypatch.setenv("REMINDER_MAX_PER_DAY", "2")
    with SessionLocal() as db:
        for i, (brand, name, model) in enumerate([("Sony", "Bravia TV", "KD-55X74L"), ("HP", "HP Laptop 15s", "15s-fq5111TU"),
                                                   ("Voltas", "Split AC", "183V"), ("Racold", "Geyser", "ETERNO PRO 25")]):
            _add(db, f"wty_rem_c{i}", brand=brand, name=name, model=model, days_left=3 + i)
        db.commit()
        stats = ns.refresh_expiry_notifications(db)
        assert stats["held_back_by_daily_cap"] >= 2  # (other tests' users may share the database)
        assert _types(db) == ["expiry_7d", "expiry_7d"]
        sent = {n.warranty_id for n in db.query(NotificationDB).filter_by(user_id=USER).all()}
        assert sent == {"wty_rem_c0", "wty_rem_c1"}  # soonest first
        # The next day (yesterday's reminders no longer count) the rest go out.
        db.query(NotificationDB).filter_by(user_id=USER).update({"created_at": datetime.utcnow() - timedelta(days=1)})
        db.commit()
        ns.refresh_expiry_notifications(db)
        assert len(_types(db)) == 4


@pytest.mark.parametrize("text,days", [
    ("Clean the air filter every two weeks.", 14), ("Print a page at least once a month.", 30),
    ("Descale the geyser every 6 months.", 180), ("Wipe the door gasket weekly.", 7),
    ("Run the drum clean cycle once a month.", 30), ("Do not expose the device to water.", None),
    ("Clean the filter regularly.", None),
])
def test_care_interval_only_when_the_text_gives_one(text, days):
    assert interval_days(text) == days


def test_care_reminders_from_guides_with_limits(monkeypatch):
    monkeypatch.setenv("REMINDER_CARE_MAX_PER_WEEK", "2")
    with SessionLocal() as db:
        _add(db, "wty_rem_ac", brand="Voltas", name="Voltas Split AC", model="183V", days_left=200)
        _add(db, "wty_rem_pr", brand="Epson", name="EcoTank L3250 Printer", model="L3250", days_left=200)
        db.add(CareGuideDB(company="Voltas", product_scope="model:183V", source_kind="manual",
                           source_url="https://www.voltas.com/remind-test", checked_by="admin", tips=[
                               {"text": "Clean the air filter every two weeks.", "quote": "Clean the air filter every two weeks.", "page": "9"},
                               {"text": "Do not block the air outlet.", "quote": "Do not block the air outlet.", "page": "9"}]))
        db.add(CareGuideDB(company="Epson", product_scope="model:L3250", source_kind="faq",
                           source_url="https://www.epson.co.in/remind-test", checked_by="admin", tips=[
                               {"text": "Print a page at least once a month.", "quote": "Print a page at least once a month.", "page": ""}]))
        db.commit()
        stats = refresh_care_reminders(db)
        assert len(_types(db)) == 2 and stats["no_interval"] >= 1  # the tip without an interval never reminds
        refresh_care_reminders(db)
        assert len(_types(db)) == 2                                   # same interval: not again
        titles = sorted(n.title for n in db.query(NotificationDB).filter_by(user_id=USER).all())
        assert titles == ["Care reminder: Epson EcoTank L3250 Printer", "Care reminder: Voltas Split AC"]
        msg = db.query(NotificationDB).filter_by(user_id=USER, warranty_id="wty_rem_ac").one().message
        assert msg == "Clean the air filter every two weeks. (From Voltas's user manual.)"
