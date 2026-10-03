"""RAG text must not move the risk score, and must read negations and counts (fix run B3)."""

import pytest

from app.db import SessionLocal
from app.db_models import WarrantyDB
from app.services import predictive, rag
from app.services.rag_signals import parse_rag_signals


@pytest.mark.parametrize(
    "text,issues,no_issue",
    [
        ("No failures reported for this model.", 0, 1),
        ("Zero errors in the last 90 days.", 0, 1),
        ("The unit has run without any issues.", 0, 1),
        ("Multiple failures reported for this model.", 2, 0),
        ("3 compressor failures reported this quarter.", 3, 0),
        ("A recall was issued for the charger.", 1, 0),
        ("Several users report display issues. No battery issues reported.", 3, 1),
    ],
)
def test_parse_rag_signals_reads_negation_and_counts(text, issues, no_issue):
    out = parse_rag_signals(text)
    assert out["issue_reports"] == issues
    assert out["no_issue_statements"] == no_issue


def test_care_signal_respects_negation():
    assert parse_rag_signals("Filter cleaned last week.")["care_reports"] == 1
    assert parse_rag_signals("No maintenance recorded.")["care_reports"] == 0


def _score(monkeypatch, user_ctx, product_ctx, flag):
    if flag:
        monkeypatch.setenv("RAG_RISK_SCORING", "1")
    else:
        monkeypatch.delenv("RAG_RISK_SCORING", raising=False)
    monkeypatch.setattr(rag, "rag_enabled", lambda: True)
    monkeypatch.setattr(
        rag,
        "build_context_multi",
        lambda db, query_text, limit, doc_types, metadata_filter: user_ctx if metadata_filter else product_ctx,
    )
    monkeypatch.setattr(
        predictive,
        "build_feature_vector",
        lambda user_id, warranty_id, product_type=None: (
            [0.0, 2.0, 1.0, 0.0, 0.0, 0.0, 0.5, 0.5, 0.5, 0.0, 0.0, 0.0],
            [],
            {"days_left": 300, "usage_hours": 120.0, "maintenance_count": 1, "error_count": 0, "failure_count": 0},
        ),
    )
    monkeypatch.setattr(predictive.predictive_model, "predict", lambda vec: ("MEDIUM", 0.4, [0.3, 0.6, 0.1]))
    monkeypatch.setattr(predictive, "compute_behaviour_risk_signal", lambda u, w: {"behaviour_risk_delta": 0.0, "reasons": []})
    return predictive.score_warranty("rag_user", "wty_rag_signals")


@pytest.fixture
def _warranty():
    with SessionLocal() as db:
        db.query(WarrantyDB).filter_by(id="wty_rag_signals").delete()
        db.add(WarrantyDB(id="wty_rag_signals", product_name="Washer", brand="Acmeco", model_code="ZX-100", region_code="IN"))
        db.commit()
    yield
    with SessionLocal() as db:
        db.query(WarrantyDB).filter_by(id="wty_rag_signals").delete()
        db.commit()


def test_rag_never_moves_score_by_default(monkeypatch, _warranty):
    none = _score(monkeypatch, "", "", flag=False)
    no_fail = _score(monkeypatch, "", "No failures reported for this model.", flag=False)
    many = _score(monkeypatch, "", "Multiple failures reported for this model.", flag=False)
    assert none["risk_score"] == no_fail["risk_score"] == many["risk_score"]
    assert not any("RAG" in r for r in many["reasons"])
    assert many["rag_context"]["issue_reports"] == 2
    assert no_fail["rag_context"]["issue_reports"] == 0 and no_fail["rag_context"]["no_issue_statements"] == 1


def test_with_flag_no_failures_and_multiple_failures_differ(monkeypatch, _warranty):
    no_fail = _score(monkeypatch, "", "No failures reported for this model.", flag=True)
    many = _score(monkeypatch, "", "Multiple failures reported for this model.", flag=True)
    baseline = _score(monkeypatch, "", "", flag=True)
    assert no_fail["risk_score"] == baseline["risk_score"]
    assert many["risk_score"] == pytest.approx(baseline["risk_score"] + 0.05)
