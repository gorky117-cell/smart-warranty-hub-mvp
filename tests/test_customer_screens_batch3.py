"""Batch 3 items 6 and 7: no model internals on customer screens; estimated periods never shown as facts."""
from datetime import date, datetime
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.db import SessionLocal
from app.db_models import UserDB
from app.deps import hash_password
from app.main import app, customer_reasons
from app.services import warranty_card

DASHBOARD = Path("templates/neo_dashboard.html").read_text(encoding="utf-8")


def test_dashboard_has_no_raw_field_dump_or_internal_labels_for_customers():
    for raw in ("`Brand: ${w.brand", "`Model: ${w.model_code", "`Serial: ${w.serial_no", "Coverage months: ${"):
        assert raw not in DASHBOARD
    assert "<summary>What is covered?</summary>" not in DASHBOARD
    # Admin-only internals.
    for label in ("Base risk score", "Behaviour delta", "Behaviour reasons"):
        line = next(l for l in DASHBOARD.splitlines() if label in l)
        assert "IS_ADMIN" in line
    tag_line = next(l for l in DASHBOARD.splitlines() if "p.action" in l and "font-size:12px" in l)
    assert "IS_ADMIN && p.action" in tag_line
    assert "predictive engine not ready yet" in DASHBOARD  # filtered by customerReasons


def test_internal_risk_reasons_are_hidden_from_customers():
    reasons = ["Predictive engine not ready yet.", "Heavy daily use in summer"]
    assert customer_reasons(reasons, is_admin=False) == ["Heavy daily use in summer"]
    assert customer_reasons(reasons, is_admin=True) == reasons


@pytest.mark.parametrize("path", ["/ui/console", "/ui/warranty-tabs"])
def test_diagnostic_pages_are_admin_only(path, monkeypatch):
    monkeypatch.setenv("RATE_LIMIT_ENABLED", "0")
    with SessionLocal() as db:
        if not db.query(UserDB).filter_by(username="screens_user").first():
            db.add(UserDB(username="screens_user", role="user", hashed_password=hash_password("secret123"), email="s@example.com"))
            db.commit()
    client = TestClient(app, follow_redirects=False)
    assert client.get(path).status_code in (302, 303, 307)  # signed out: sign in first
    client.post("/auth/login", data={"username": "screens_user", "password": "secret123"})
    resp = client.get(path)
    assert resp.status_code == 303 and resp.headers["location"] == "/ui/neo-dashboard"


def _w(product, model=None, coverage=12, conf=None):
    return SimpleNamespace(brand="Voltas", product_name=product, model_code=model, purchase_date=datetime(2025, 4, 22),
                           coverage_months=coverage, expiry_date=None, terms=["Compressor is covered for 5 years."],
                           exclusions=[], claim_steps=[], alternatives={}, confidence=conf or {})


ESTIMATED = {"status": "estimated"}
CONFIRMED = {"status": "confirmed"}


@pytest.mark.parametrize("product", ["Voltas 1.5 Ton Window AC", "LG 242 L Double Door Refrigerator", "Bosch 7 kg Front Load Washing Machine"])
def test_split_warranty_products_get_the_no_numbers_sentence(product):
    card = warranty_card.five_lines(_w(product), ESTIMATED, None, today=date(2025, 6, 1))
    first = card["lines"][0]
    assert first["text"] == warranty_card.SPLIT_WARRANTY_TEXT and first["confirm"]
    assert not any(ch.isdigit() for line in card["lines"][:3] for ch in line["text"])
    assert not any("5 years" in x["text"] for x in card["extras"])


@pytest.mark.parametrize("product", ["Samsung Galaxy M17e Mobile Phone", "HP Laptop 15s", "Epson L3250 Printer", "Philips Mixer Grinder"])
def test_other_products_get_a_plain_unknown_period(product):
    card = warranty_card.five_lines(_w(product), {"status": "not_confirmed"}, None, today=date(2025, 6, 1))
    assert card["lines"][0]["text"] == warranty_card.UNKNOWN_PERIOD_TEXT


def test_confirmed_terms_or_invoice_stated_periods_are_still_shown():
    card = warranty_card.five_lines(_w("Voltas 1.5 Ton Window AC"), CONFIRMED, None, today=date(2025, 6, 1))
    assert card["lines"][0]["text"].startswith("Covered until 22 Apr 2026") and card["period_note"] is None
    stated = _w("Voltas 1.5 Ton Window AC", conf={"coverage_months": 0.7})  # printed on the invoice
    card = warranty_card.five_lines(stated, ESTIMATED, None, today=date(2025, 6, 1))
    assert card["lines"][0]["text"].startswith("Covered until 22 Apr 2026")


def test_dashboard_shows_no_end_date_for_estimates():
    assert "End date: check your warranty card" in DASHBOARD and "w.period_note" in DASHBOARD
