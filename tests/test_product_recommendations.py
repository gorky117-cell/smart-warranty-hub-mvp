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
    # SWH's own reasons, in plain words (2026-10-06): no filler such as "general care advice".
    assert "print head" in reasons and "general care" not in reasons and "oem" not in reasons


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


def test_broader_product_categories_get_specific_safe_care():
    cases = [
        ("Oil room heater", "heater", "socket"),
        ("Electric geyser water heater", "water_heater", "pressure"),
        ("Ceiling fan", "fan", "blade"),
        ("Split AC air conditioner", "air_conditioner", "filter"),
        ("Front load washing machine", "washing_machine", "drum"),
        ("Microwave oven", "microwave", "container"),
        ("Mirrorless camera", "camera", "lens"),
        ("Wi-Fi router", "router", "firmware"),
        ("Smartwatch wearable", "wearable", "sensor"),
        ("Bluetooth speaker", "audio", "volume"),
        ("RO water purifier", "purifier", "filter"),
        ("Mixer grinder food processor", "kitchen_appliance", "motor"),
        ("Desert air cooler", "cooler", "water"),
        ("Home inverter UPS", "inverter", "load"),
    ]

    for product_name, expected_category, expected_word in cases:
        recs = build_product_recommendations(
            user_id="u1",
            warranty_id="w1",
            region="IN",
            warranty={"product_name": product_name},
            predictive={"risk_label": "MEDIUM"},
        )
        assert recs[0]["category"] == expected_category
        text = " ".join((rec["title"] + " " + rec["why"]).lower() for rec in recs)
        assert expected_word in text
        assert "free repair" not in text
        assert "claim eligible" not in text


def test_product_recommendations_do_not_echo_weak_risk_context_as_cause():
    recs = build_product_recommendations(
        user_id="u1",
        warranty_id="w1",
        region="IN",
        warranty={"product_name": "Samsung Galaxy M17e 5G Mobile"},
        predictive={
            "risk_label": "MEDIUM",
            "reasons": ["Device is relatively new.", "No maintenance recorded."],
            "context_gaps": ["No maintenance recorded."],
        },
    )

    text = " ".join(rec["why"].lower() for rec in recs)

    assert "smartphone" == recs[0]["category"]
    assert "relatively new" not in text
    assert "no maintenance recorded" not in text
    assert "more usage context" in text


def test_oem_facts_create_source_labeled_phone_care():
    recs = build_product_recommendations(
        user_id="u1",
        warranty_id="w1",
        region="IN",
        warranty={
            "product_name": "Samsung Galaxy M17e 5G Mobile",
            "terms": ["Standard coverage for 12 months from purchase date."],
            "exclusions": ["Screen protector repair/replacement is not covered by Samsung Limited Warranty policy."],
            "claim_steps": ["Warranty Checker", "Service Centre"],
            "alternatives": {"terms_source_url": "https://www.samsung.com/in/support/warranty/"},
        },
        predictive={"risk_label": "MEDIUM"},
    )

    titles = " ".join(rec["title"].lower() for rec in recs)
    labels = {rec.get("source_label") for rec in recs}

    # Ordered by care priority (live test 1): protecting the screen comes before paperwork.
    assert recs[0]["title"] == "Protect the screen and body" and recs[0]["source_label"] == "From the warranty terms"
    assert "claim documents" in titles
    assert "From the claim steps" in labels
    assert any(rec.get("source_label") == "Smart Warranty Hub care tip" for rec in recs)


def test_oem_facts_create_source_labeled_printer_care():
    recs = build_product_recommendations(
        user_id="u1",
        warranty_id="w1",
        region="IN",
        warranty={
            "product_name": "Epson L3250 Printer",
            "model_code": "L3250",
            "terms": [
                "Warranty coverage is up to 1 year or 30,000 prints, whichever comes first.",
                "Printhead coverage follows Epson warranty terms.",
            ],
            "claim_steps": ["Contact Epson service center with invoice and serial number."],
            "alternatives": {"terms_source_url": "https://www.epson.co.in/support/warranty"},
        },
        predictive={"risk_label": "MEDIUM"},
    )

    titles = " ".join(rec["title"].lower() for rec in recs)
    labels = {rec.get("source_label") for rec in recs}

    assert "printhead" in titles
    assert "usage limits" in titles
    assert "From the warranty terms" in labels
    assert "From the claim steps" in labels
