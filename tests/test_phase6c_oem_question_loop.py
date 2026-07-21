from app.services import oem_question_service


def test_oem_question_answer_stats_suppresses_small_cohort(tmp_path, monkeypatch):
    monkeypatch.setattr(oem_question_service, "QUESTIONS_PATH", str(tmp_path / "questions.jsonl"))
    monkeypatch.setattr(oem_question_service, "ANSWERS_PATH", str(tmp_path / "answers.jsonl"))

    q = oem_question_service.publish_question(
        {"brand": "LoopBrand", "model_code": "L1", "product_type": "washer", "region": "IN"},
        {"text": "Do you use a stabilizer?", "answer_type": "choice", "options": ["Yes", "No"]},
    )
    oem_question_service.record_oem_answer("u1", "w1", q["id"], "Yes")

    out = oem_question_service.aggregate_answers({"brand": "LoopBrand"}, min_cohort=2)

    assert out["status"] == "suppressed"
    assert out["cohort_size"] == 1
    assert out["question_count"] == 1


def test_oem_question_answer_stats_returns_aggregate_counts(tmp_path, monkeypatch):
    monkeypatch.setattr(oem_question_service, "QUESTIONS_PATH", str(tmp_path / "questions.jsonl"))
    monkeypatch.setattr(oem_question_service, "ANSWERS_PATH", str(tmp_path / "answers.jsonl"))

    q = oem_question_service.publish_question(
        {"brand": "LoopBrand", "model_code": "L1", "product_type": "washer", "region": "IN"},
        {"text": "Do you use a stabilizer?", "answer_type": "choice", "options": ["Yes", "No"]},
    )
    for idx, answer in enumerate(["Yes", "No", "Yes"], start=1):
        oem_question_service.record_oem_answer(f"u{idx}", f"w{idx}", q["id"], answer)

    out = oem_question_service.aggregate_answers({"brand": "LoopBrand"}, min_cohort=3)

    assert out["status"] == "ok"
    assert out["cohort_size"] == 3
    assert out["items"][0]["response_count"] == 3
    assert out["items"][0]["top_answers"][0] == {"answer": "Yes", "count": 2}
    assert out["privacy_note"].startswith("Aggregated answers only")
