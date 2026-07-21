from app.services import oem_recommendation_service, product_recommendations


def test_product_interest_stats_suppresses_small_cohort(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    product_recommendations.record_product_interest_event(
        {"user_id": "u1", "warranty_id": "w1", "product_id": "p1", "title": "Plan", "action": "view", "region": "IN"}
    )

    out = product_recommendations.aggregate_product_interest_stats(region="IN", min_cohort=2)

    assert out["status"] == "suppressed"
    assert out["cohort_size"] == 1


def test_product_interest_stats_returns_aggregate_counts(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    for idx, action in enumerate(["view", "click", "view"], start=1):
        product_recommendations.record_product_interest_event(
            {
                "user_id": f"u{idx}",
                "warranty_id": f"w{idx}",
                "product_id": "p1",
                "title": "Extended warranty",
                "action": action,
                "risk_band": "HIGH",
                "region": "IN",
            }
        )

    out = product_recommendations.aggregate_product_interest_stats(region="IN", min_cohort=3)

    assert out["status"] == "ok"
    assert out["cohort_size"] == 3
    assert out["event_count"] == 3
    assert out["items"][0]["product_id"] == "p1"
    assert out["items"][0]["actions"]["view"] == 2
    assert out["action_counts"]["click"] == 1


def test_oem_recommendation_stats_combines_active_recs_and_demand(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(oem_recommendation_service, "REC_PATH", tmp_path / "data" / "oem_recommendations.jsonl")
    oem_recommendation_service.publish_recommendation(
        {"brand": "RecBrand", "model": "R1", "region": "IN", "title": "Care plan", "message": "Use care plan"}
    )
    for idx in range(3):
        product_recommendations.record_product_interest_event(
            {
                "user_id": f"u{idx}",
                "warranty_id": f"w{idx}",
                "product_id": "care_plan",
                "title": "Care plan",
                "action": "click",
                "region": "IN",
            }
        )

    out = oem_recommendation_service.aggregate_stats({"brand": "RecBrand", "model": "R1", "region": "IN"}, min_cohort=3)

    assert out["status"] == "ok"
    assert out["active_recommendation_count"] == 1
    assert out["product_interest"][0]["product_id"] == "care_plan"
    assert out["recommendation_opportunities"]
    assert out["privacy_note"].startswith("Aggregated recommendation demand")
