"""One risk scorer for every endpoint (fix run B9)."""

from datetime import datetime

from fastapi.testclient import TestClient

from app.db import SessionLocal
from app.db_models import NudgeEvents, WarrantyDB, WarrantyOwnerDB
from app.main import app
from app.models import BehaviourEvent
from app.services import predictive
from app.storage import store

WID = "wty_unified_risk"


def _fixed_model(monkeypatch, label="LOW", score=0.2):
    monkeypatch.setattr(
        predictive,
        "build_feature_vector",
        lambda user_id, warranty_id, product_type=None: (
            [0.0] * 12,
            [],
            {"days_left": 300, "usage_hours": 50.0, "maintenance_count": 1, "error_count": 0, "failure_count": 0},
        ),
    )
    monkeypatch.setattr(predictive.predictive_model, "predict", lambda vec: (label, score, [0.7, 0.2, 0.1]))
    monkeypatch.setattr(predictive, "compute_behaviour_risk_signal", lambda u, w: {"behaviour_risk_delta": 0.0, "reasons": []})


def _seed():
    with SessionLocal() as db:
        db.query(NudgeEvents).filter_by(warranty_id=WID).delete()
        db.query(WarrantyDB).filter_by(id=WID).delete()
        db.add(WarrantyDB(id=WID, product_name="Washer", brand="Acmeco", model_code="ZX-100"))
        if not db.query(WarrantyOwnerDB).filter_by(user_id="admin", warranty_id=WID).first():
            db.add(WarrantyOwnerDB(user_id="admin", warranty_id=WID))
        db.commit()
    store.behaviour_events.pop(f"admin:{WID}", None)
    store.warranties.pop(WID, None)


def test_endpoints_agree_with_ml_scorer(monkeypatch):
    _fixed_model(monkeypatch, "MEDIUM", 0.45)
    _seed()
    client = TestClient(app)
    token = client.post("/auth/login", data={"username": "admin", "password": "admin123"}, headers={"accept": "application/json"}).json()["access_token"]
    auth = {"Authorization": f"Bearer {token}"}

    ml = predictive.score_warranty("admin", WID)
    risk = client.post("/risk/score", json={"warranty_id": WID, "user_id": "admin"}, headers=auth).json()
    adv = client.get(f"/advisories/{WID}?user_id=admin", headers=auth).json()

    assert risk["source"] == "predictive" and adv["risk"]["source"] == "predictive"
    assert risk["value"] == adv["risk"]["value"] == ml["risk_score"]
    assert risk["band"] == adv["risk"]["band"] == ml["risk_label"].lower()


def test_nudge_engagement_and_reported_issues_move_the_ml_score(monkeypatch):
    _fixed_model(monkeypatch)
    _seed()
    base = predictive.score_warranty("admin", WID)["risk_score"]

    with SessionLocal() as db:
        for _ in range(3):
            db.add(NudgeEvents(user_id="admin", warranty_id=WID, variant="A", nudge_type="care", shown_at=datetime.utcnow(), ignored_at=datetime.utcnow()))
        db.commit()
    ignored = predictive.score_warranty("admin", WID)
    assert ignored["engagement"]["nudges_dismissed"] == 3
    assert ignored["risk_score"] == round(base + 0.09, 3)

    store.behaviour_events[f"admin:{WID}"] = [
        BehaviourEvent(user_id="admin", warranty_id=WID, event_type="issue_reported")
    ]
    reported = predictive.score_warranty("admin", WID)
    assert reported["engagement"]["issues_reported"] == 1
    assert any("reported an issue" in r for r in reported["reasons"])
    assert reported["risk_score"] > ignored["risk_score"]
    store.behaviour_events.pop(f"admin:{WID}", None)


def test_heuristic_is_only_a_fallback(monkeypatch):
    _seed()
    monkeypatch.setattr(predictive, "score_warranty", lambda u, w, product_type=None: {"risk_label": "UNKNOWN"})
    risk = predictive.unified_risk("admin", WID)
    assert risk.source == "heuristic_fallback"
    monkeypatch.setattr(predictive, "score_warranty", lambda u, w, product_type=None: (_ for _ in ()).throw(RuntimeError()))
    assert predictive.unified_risk("admin", WID).source == "heuristic_fallback"
