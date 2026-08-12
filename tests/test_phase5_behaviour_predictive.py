from app.models import TelemetryEvent
from app.services import behaviour_questions, predictive


class _Warranty:
    def __init__(
        self,
        serial_no="SN-1",
        region_code="IN",
        product_name="Unknown product",
        product_type=None,
        model_code=None,
        brand=None,
        terms=None,
        exclusions=None,
        claim_steps=None,
        alternatives=None,
    ):
        self.serial_no = serial_no
        self.region_code = region_code
        self.product_name = product_name
        self.product_type = product_type
        self.model_code = model_code
        self.brand = brand
        self.terms = terms or []
        self.exclusions = exclusions or []
        self.claim_steps = claim_steps or []
        self.alternatives = alternatives or {}


def test_useful_question_prefers_missing_serial_and_returns_one_question(tmp_path, monkeypatch):
    monkeypatch.setattr(behaviour_questions, "DATA_PATH", str(tmp_path / "answers.jsonl"))

    q, done, reason = behaviour_questions.get_next_useful_question(
        "phase5_user",
        "phase5_warranty",
        warranty=_Warranty(serial_no=None, region_code="IN"),
        telemetry_events=[],
    )

    assert done is False
    assert q["id"] == "q0_serial"
    assert reason == "serial_missing"


def test_useful_question_stops_when_context_is_complete_and_answered(tmp_path, monkeypatch):
    data_path = tmp_path / "answers.jsonl"
    monkeypatch.setattr(behaviour_questions, "DATA_PATH", str(data_path))
    for qid in ("q2_daily_usage", "q1_usage_location"):
        behaviour_questions.record_answer("phase5_done_user", "phase5_done_warranty", qid, "Done")

    q, done, reason = behaviour_questions.get_next_useful_question(
        "phase5_done_user",
        "phase5_done_warranty",
        warranty=_Warranty(serial_no="SN-1", region_code="IN"),
        telemetry_events=[
            TelemetryEvent(
                id="tel_phase5_usage",
                user_id="phase5_done_user",
                warranty_id="phase5_done_warranty",
                event_type="usage",
                payload={"hours": 10, "errors": 0},
            )
        ],
    )

    assert q is None
    assert done is True
    assert reason == "no_useful_question"


def test_useful_question_asks_voltage_only_when_signal_exists(tmp_path, monkeypatch):
    monkeypatch.setattr(behaviour_questions, "DATA_PATH", str(tmp_path / "answers.jsonl"))

    q, done, reason = behaviour_questions.get_next_useful_question(
        "phase5_voltage_user",
        "phase5_voltage_warranty",
        warranty=_Warranty(serial_no="SN-1", region_code="IN"),
        telemetry_events=[
            TelemetryEvent(
                id="tel_phase5_voltage",
                user_id="phase5_voltage_user",
                warranty_id="phase5_voltage_warranty",
                event_type="usage",
                payload={"hours": 20, "voltage": 270},
            )
        ],
    )

    assert done is False
    assert q["id"] == "q3_voltage"
    assert reason == "voltage_issue_reported"


def test_useful_question_uses_product_specific_printer_context_before_region(tmp_path, monkeypatch):
    monkeypatch.setattr(behaviour_questions, "DATA_PATH", str(tmp_path / "answers.jsonl"))

    q, done, reason = behaviour_questions.get_next_useful_question(
        "phase5_printer_user",
        "phase5_printer_warranty",
        warranty=_Warranty(serial_no="SN-1", region_code=None, product_name="Epson L3250 Printer"),
        telemetry_events=[],
    )

    assert done is False
    assert q["id"] == "pq_printer_dry_ink"
    assert "printer" in q["tags"]
    assert reason == "printer_behaviour_context_needed"


def test_useful_question_prefers_official_oem_care_context_when_available(tmp_path, monkeypatch):
    monkeypatch.setattr(behaviour_questions, "DATA_PATH", str(tmp_path / "answers.jsonl"))

    q, done, reason = behaviour_questions.get_next_useful_question(
        "phase5_oem_user",
        "phase5_oem_warranty",
        warranty=_Warranty(
            serial_no="SN-1",
            region_code="IN",
            product_name="Epson L3250 Printer",
            terms=[
                "Enjoy warranty coverage of up to 1 years or 30,000 prints, whichever comes first.",
                "Epson warranty includes coverage of printhead.",
            ],
            alternatives={"terms_source_type": "approved_oem_source", "terms_source_url": "https://www.epson.co.in/product"},
        ),
        telemetry_events=[],
    )

    assert done is False
    assert q["id"] == "oq_usage_limit"
    assert q["source"] == "official_oem_terms"
    assert reason == "official_oem_care_context_needed"


def test_useful_question_uses_product_specific_oem_usage_wording(tmp_path, monkeypatch):
    monkeypatch.setattr(behaviour_questions, "DATA_PATH", str(tmp_path / "answers.jsonl"))

    q, done, reason = behaviour_questions.get_next_useful_question(
        "phase5_printer_usage_user",
        "phase5_printer_usage_warranty",
        warranty=_Warranty(
            serial_no="SN-1",
            region_code="IN",
            product_name="Epson L3250 Printer",
            terms=["Warranty coverage is up to 1 year or 30,000 prints, whichever comes first."],
            alternatives={
                "terms_source_type": "approved_oem_source",
                "terms_source_url": "https://www.epson.co.in/support/warranty",
            },
        ),
        telemetry_events=[],
    )

    assert done is False
    assert q["id"] == "oq_usage_limit"
    assert "printer" in q["text"].lower()
    assert "used heavily" in q["text"].lower()
    assert reason == "official_oem_care_context_needed"


def test_useful_question_blocks_irrelevant_oem_filter_prompt_for_phone(tmp_path, monkeypatch):
    monkeypatch.setattr(behaviour_questions, "DATA_PATH", str(tmp_path / "answers.jsonl"))

    q, done, reason = behaviour_questions.get_next_useful_question(
        "phase5_phone_oem_user",
        "phase5_phone_oem_warranty",
        warranty=_Warranty(
            serial_no="SN-1",
            region_code="IN",
            product_name="Samsung Galaxy M17e 5G Mobile",
            brand="Samsung",
            model_code="M17E",
            terms=["Limited warranty period of 1 year applies."],
            exclusions=[
                "This Warranty does not cover service costs in replacing consumable parts such as filters, lamps, and other parts."
            ],
            alternatives={
                "terms_source_type": "approved_oem_source",
                "terms_source_url": "https://www.samsung.com/in/support/warranty/",
            },
        ),
        telemetry_events=[],
    )

    assert done is False
    assert q["id"] == "pq_phone_overheat"
    assert q.get("source") != "official_oem_terms"
    assert reason == "smartphone_behaviour_context_needed"


def test_useful_question_uses_phone_specific_oem_service_route(tmp_path, monkeypatch):
    monkeypatch.setattr(behaviour_questions, "DATA_PATH", str(tmp_path / "answers.jsonl"))

    q, done, reason = behaviour_questions.get_next_useful_question(
        "phase5_phone_service_user",
        "phase5_phone_service_warranty",
        warranty=_Warranty(
            serial_no="SN-1",
            region_code="IN",
            product_name="Samsung Galaxy M17e 5G Mobile",
            brand="Samsung",
            model_code="M17E",
            claim_steps=["Warranty Check", "Detailed cost can be confirmed at a Samsung Authorized Service Center."],
            alternatives={
                "terms_source_type": "approved_oem_source",
                "terms_source_url": "https://www.samsung.com/in/support/warranty/",
            },
        ),
        telemetry_events=[],
    )

    assert done is False
    assert q["id"] == "oq_service_route"
    assert q["source"] == "official_oem_terms"
    assert "phone claim" in q["text"].lower()
    assert "imei/serial" in q["text"].lower()
    assert reason == "official_oem_care_context_needed"


def test_useful_question_allows_oem_filter_prompt_for_purifier(tmp_path, monkeypatch):
    monkeypatch.setattr(behaviour_questions, "DATA_PATH", str(tmp_path / "answers.jsonl"))

    q, done, reason = behaviour_questions.get_next_useful_question(
        "phase5_purifier_oem_user",
        "phase5_purifier_oem_warranty",
        warranty=_Warranty(
            serial_no="SN-1",
            region_code="IN",
            product_name="RO water purifier",
            terms=["Warranty requires filter or cartridge care according to OEM maintenance guidance."],
            alternatives={
                "terms_source_type": "approved_oem_source",
                "terms_source_url": "https://example-oem.test/support/warranty",
            },
        ),
        telemetry_events=[],
    )

    assert done is False
    assert q["id"] == "oq_filter"
    assert q["source"] == "official_oem_terms"
    assert reason == "official_oem_care_context_needed"


def test_useful_question_does_not_treat_unconfirmed_terms_as_oem_care_context(tmp_path, monkeypatch):
    monkeypatch.setattr(behaviour_questions, "DATA_PATH", str(tmp_path / "answers.jsonl"))

    q, done, reason = behaviour_questions.get_next_useful_question(
        "phase5_unconfirmed_user",
        "phase5_unconfirmed_warranty",
        warranty=_Warranty(
            serial_no="SN-1",
            region_code="IN",
            product_name="Epson L3250 Printer",
            terms=["30,000 prints and printhead mentioned in an unconfirmed record."],
            alternatives={"terms_source_type": "default_rules", "terms_source_url": "internal://default_rules"},
        ),
        telemetry_events=[],
    )

    assert done is False
    assert q["id"] == "pq_printer_dry_ink"
    assert "source" not in q
    assert reason == "printer_behaviour_context_needed"


def test_useful_question_uses_product_specific_geyser_context(tmp_path, monkeypatch):
    monkeypatch.setattr(behaviour_questions, "DATA_PATH", str(tmp_path / "answers.jsonl"))

    q, done, reason = behaviour_questions.get_next_useful_question(
        "phase5_geyser_user",
        "phase5_geyser_warranty",
        warranty=_Warranty(serial_no="SN-1", region_code="IN", product_name="Electric geyser water heater"),
        telemetry_events=[],
    )

    assert done is False
    assert q["id"] == "pq_geyser_leak"
    assert "water_heater" in q["tags"]
    assert reason == "water_heater_behaviour_context_needed"


def test_useful_question_unknown_product_keeps_safe_general_context(tmp_path, monkeypatch):
    data_path = tmp_path / "answers.jsonl"
    monkeypatch.setattr(behaviour_questions, "DATA_PATH", str(data_path))
    behaviour_questions.record_answer("phase5_unknown_user", "phase5_unknown_warranty", "q2_daily_usage", "Low")
    behaviour_questions.record_answer("phase5_unknown_user", "phase5_unknown_warranty", "q1_usage_location", "Home")

    q, done, reason = behaviour_questions.get_next_useful_question(
        "phase5_unknown_user",
        "phase5_unknown_warranty",
        warranty=_Warranty(serial_no="SN-1", region_code="IN", product_name="Unknown product"),
        telemetry_events=[TelemetryEvent(id="tel_unknown", user_id="u", warranty_id="w", event_type="usage", payload={"hours": 5})],
    )

    assert q is None
    assert done is True
    assert reason == "no_useful_question"


def test_predictive_output_keeps_legal_warranty_separate(monkeypatch):
    monkeypatch.setattr(
        predictive,
        "build_feature_vector",
        lambda user_id, warranty_id, product_type=None: ([0.0] * 12, [], {"days_left": 20, "maintenance_count": 0}),
    )
    monkeypatch.setattr(
        predictive.predictive_model,
        "predict",
        lambda vec: ("MEDIUM", 0.5, [0.2, 0.5, 0.3]),
    )
    monkeypatch.setattr(
        predictive,
        "compute_behaviour_risk_signal",
        lambda user_id, warranty_id: {
            "behaviour_risk_delta": 0.1,
            "reasons": ["Heavy use (1200 hrs recent window)"],
        },
    )

    out = predictive.score_warranty("phase5_pred_user", "phase5_pred_warranty")

    assert out["legal_warranty_separate"] is True
    assert out["disclaimer"] == "Care signal, not a guaranteed product failure prediction."
    assert out["base_risk_score"] == 0.5
    assert out["behaviour_delta"] == 0.1
    assert "risk_reason_breakdown" in out


def test_predictive_no_device_evidence_stays_low_risk(monkeypatch):
    """A newly onboarded product with no history must not be called risky.

    Absence of telemetry/usage/maintenance history is not evidence of failure, so
    the label stays LOW and the missing inputs are reported as context gaps.
    """
    monkeypatch.setattr(
        predictive,
        "build_feature_vector",
        lambda user_id, warranty_id, product_type=None: (
            [0.0, 2.0, 1.0, 0.0, 0.0, 0.0, 0.5, 0.5, 0.5, 0.0, 0.0, 0.0],
            [],
            {"days_left": 300, "maintenance_count": 0, "error_count": 0, "failure_count": 0},
        ),
    )
    monkeypatch.setattr(
        predictive.predictive_model,
        "predict",
        lambda vec: ("HIGH", 0.9, [0.05, 0.05, 0.9]),
    )
    monkeypatch.setattr(
        predictive,
        "compute_behaviour_risk_signal",
        lambda user_id, warranty_id: {"behaviour_risk_delta": 0.0, "reasons": []},
    )
    monkeypatch.setattr(
        predictive,
        "SessionLocal",
        lambda: (_ for _ in ()).throw(RuntimeError("skip db signals")),
    )

    out = predictive.score_warranty("phase5_context_user", "phase5_context_warranty")

    assert out["risk_label"] == "LOW"
    assert out["risk_score"] == predictive.NO_EVIDENCE_MAX_SCORE
    assert "Not enough usage history yet to assess risk." in out["context_gaps"]
    assert "No maintenance recorded." in out["context_gaps"]
    assert "No maintenance recorded." not in out["reasons"]


def test_predictive_usage_history_without_issues_caps_at_medium(monkeypatch):
    """With real usage history but no issue signals, cap at MEDIUM (not HIGH)."""
    monkeypatch.setattr(
        predictive,
        "build_feature_vector",
        lambda user_id, warranty_id, product_type=None: (
            [0.0, 2.0, 1.0, 0.0, 0.0, 0.0, 0.5, 0.5, 0.5, 0.0, 0.0, 0.0],
            [],
            {
                "days_left": 300,
                "maintenance_count": 0,
                "error_count": 0,
                "failure_count": 0,
                "usage_hours": 120.0,
            },
        ),
    )
    monkeypatch.setattr(
        predictive.predictive_model,
        "predict",
        lambda vec: ("HIGH", 0.9, [0.05, 0.05, 0.9]),
    )
    monkeypatch.setattr(
        predictive,
        "compute_behaviour_risk_signal",
        lambda user_id, warranty_id: {
            "behaviour_risk_delta": 0.03,
            "reasons": ["Moderate usage (40 hrs avg recent)"],
        },
    )
    monkeypatch.setattr(
        predictive,
        "SessionLocal",
        lambda: (_ for _ in ()).throw(RuntimeError("skip db signals")),
    )

    out = predictive.score_warranty("phase5_moderate_user", "phase5_moderate_warranty")

    # Moderate usage is not an issue signal, so it must not unlock HIGH.
    assert out["risk_label"] == "MEDIUM"
    assert out["risk_score"] == 0.66


def test_predictive_aggregate_oem_context_alone_does_not_unlock_high(monkeypatch):
    """Generic 'OEM issue signals present' must not justify HIGH on its own."""
    assert predictive._reason_is_real_risk_signal(
        "OEM issue signals present (avg severity 0.50)"
    ) is False
    assert predictive._reason_is_real_risk_signal(
        "RAG signals show recent issues for this product/user."
    ) is False
    # Device-specific evidence still counts.
    assert predictive._reason_is_real_risk_signal("Multiple errors recorded.") is True
    assert predictive._reason_is_real_risk_signal("Past breakdowns detected.") is True
    assert predictive._reason_is_real_risk_signal("Warranty is close to expiry.") is True


def test_predictive_real_errors_can_remain_high_risk(monkeypatch):
    monkeypatch.setattr(
        predictive,
        "build_feature_vector",
        lambda user_id, warranty_id, product_type=None: (
            [0.0, 18.0, 5.0, 4.0, 0.0, 0.0, 0.5, 0.5, 0.5, 0.0, 0.0, 0.0],
            [],
            {"days_left": 300, "maintenance_count": 0, "error_count": 4, "failure_count": 0},
        ),
    )
    monkeypatch.setattr(
        predictive.predictive_model,
        "predict",
        lambda vec: ("HIGH", 0.9, [0.05, 0.05, 0.9]),
    )
    monkeypatch.setattr(
        predictive,
        "compute_behaviour_risk_signal",
        lambda user_id, warranty_id: {"behaviour_risk_delta": 0.0, "reasons": []},
    )
    monkeypatch.setattr(
        predictive,
        "SessionLocal",
        lambda: (_ for _ in ()).throw(RuntimeError("skip db signals")),
    )

    out = predictive.score_warranty("phase5_error_user", "phase5_error_warranty")

    assert out["risk_label"] == "HIGH"
    assert any("Multiple errors" in reason for reason in out["reasons"])
