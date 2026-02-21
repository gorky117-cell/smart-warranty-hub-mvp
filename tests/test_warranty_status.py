from datetime import date, timedelta

from app.models import CanonicalWarranty, RiskScore
from app.services.nudge import generate_nudges
from app.services.warranty_status import compute_warranty_status
from app.storage import store


def test_warranty_status_expired_reports_lapse_and_not_eligible():
    today = date(2026, 2, 21)
    status = compute_warranty_status(
        purchase_date=date(2023, 1, 1),
        coverage_months=12,
        expiry_date=date(2024, 1, 1),
        today=today,
    )
    assert status["status"] == "expired"
    assert status["claim_eligibility"] == "not_eligible"
    assert status["days_lapsed"] > 0
    assert status["lapsed_text"] is not None


def test_warranty_status_derives_expiry_from_purchase_and_coverage():
    status = compute_warranty_status(
        purchase_date=date(2025, 1, 1),
        coverage_months=24,
        expiry_date=None,
        today=date(2025, 6, 1),
    )
    assert status["status"] in ("active", "expiring_soon")
    assert status["expiry_source"] == "derived_from_purchase_plus_coverage"
    assert status["expiry_date_used"] == "2027-01-01"


def test_warranty_status_unknown_when_dates_missing():
    status = compute_warranty_status(
        purchase_date=None,
        coverage_months=None,
        expiry_date=None,
        today=date(2026, 1, 1),
    )
    assert status["status"] == "unknown"
    assert status["claim_eligibility"] == "review"


def test_generate_nudges_shows_lapsed_message_for_expired_warranty():
    warranty_id = "wty_lapsed_01"
    user_id = "user_lapsed_01"
    store.warranties[warranty_id] = CanonicalWarranty(
        id=warranty_id,
        brand="TestBrand",
        model_code="M-1",
        purchase_date=date.today() - timedelta(days=800),
        coverage_months=12,
        expiry_date=None,  # nudge must derive expiry from purchase + coverage
    )
    risk = RiskScore(
        warranty_id=warranty_id,
        user_id=user_id,
        value=0.8,
        band="high",
        contributors={},
    )
    nudges = generate_nudges(risk, variant="A")
    joined = " ".join([n.title + " " + n.message for n in nudges]).lower()
    assert "lapsed" in joined
    assert "not eligible" in joined
