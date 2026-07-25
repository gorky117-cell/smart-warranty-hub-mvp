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
    ):
        self.serial_no = serial_no
        self.region_code = region_code
        self.product_name = product_name
        self.product_type = product_type
        self.model_code = model_code
        self.brand = brand


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
