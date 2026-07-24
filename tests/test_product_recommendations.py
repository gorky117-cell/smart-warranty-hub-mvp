from app.services.product_recommendations import build_product_recommendations


def test_printer_recommendations_are_product_aware_not_generic_backup():
    recs = build_product_recommendations(
        user_id="u1",
        warranty_id="w1",
        region="IN",
        warranty={"product_name": "Epson L3250 Printer", "model_code": "L3250"},
        predictive={"risk_label": "HIGH", "behaviour_reasons": ["Light to moderate daily use."]},
    )

    titles = " ".join(rec["title"].lower() for rec in recs)
    reasons = " ".join(rec["why"].lower() for rec in recs)

    assert "backup" not in titles
    assert "sync" not in titles
    assert "ink" in titles
    assert "nozzle" in titles
    assert "print" in titles
    assert "general care" in reasons
    assert "warranty coverage promise" in reasons


def test_unknown_product_recommendations_stay_safe_and_general():
    recs = build_product_recommendations(
        user_id="u1",
        warranty_id="w1",
        region="IN",
        warranty={"product_name": "Unknown Device", "model_code": "X100"},
        predictive={"risk_score": 0.2},
    )

    text = " ".join((rec["title"] + " " + rec["why"]).lower() for rec in recs)

    assert "invoice" in text
    assert "serial" in text
    assert "free repair" not in text
    assert "claim eligible" not in text
    assert "covered by warranty" not in text

