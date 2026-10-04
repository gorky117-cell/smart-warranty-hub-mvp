"""Customer confirmations/corrections are logged locally only when CORRECTIONS_LOG=1, without personal data."""

import csv

from fastapi.testclient import TestClient

from app.db import SessionLocal
from app.db_models import WarrantyDB
from app.main import app
from app.services import corrections_log


def _seed(wid):
    with SessionLocal() as db:
        db.query(WarrantyDB).filter_by(id=wid).delete()
        db.add(WarrantyDB(id=wid, product_name="Product", confidence={}, alternatives={
            "brand_suggestion": {"value": "Lo", "status": "pending"},
            "model_suggestion": {"value": "OLEDSS-002", "status": "pending"},
            "serial_suggestion": {"value": "SNO01X1001", "status": "pending"},
        }))
        db.commit()


def _client():
    client = TestClient(app)
    token = client.post("/auth/login", data={"username": "admin", "password": "admin123"}, headers={"accept": "application/json"}).json()["access_token"]
    return client, {"Authorization": f"Bearer {token}"}


def test_off_by_default_writes_nothing(tmp_path, monkeypatch):
    monkeypatch.delenv("CORRECTIONS_LOG", raising=False)
    monkeypatch.setenv("CORRECTIONS_LOG_PATH", str(tmp_path / "corrections.csv"))
    _seed("wty_corr_off")
    client, auth = _client()
    assert client.post("/warranties/wty_corr_off/field-suggestion", json={"field": "brand", "action": "confirm", "value": "LG"}, headers=auth).status_code == 200
    assert not (tmp_path / "corrections.csv").exists()


def test_confirmations_and_corrections_are_logged_without_personal_data(tmp_path, monkeypatch):
    path = tmp_path / "corrections.csv"
    monkeypatch.setenv("CORRECTIONS_LOG", "1")
    monkeypatch.setenv("CORRECTIONS_LOG_PATH", str(path))
    _seed("wty_corr_on")
    client, auth = _client()
    url = "/warranties/wty_corr_on/field-suggestion"
    client.post(url, json={"field": "brand", "action": "confirm", "value": "LG"}, headers=auth)
    client.post(url, json={"field": "model_code", "action": "confirm", "value": "OLEDSS-002"}, headers=auth)
    client.post("/warranties/wty_corr_on/serial-suggestion", json={"action": "dismiss"}, headers=auth)
    client.post("/warranties/wty_corr_on/manual-details", json={"product_name": "Call 9876543210 OLED TV", "purchase_date": "2025-01-11"}, headers=auth)
    rows = list(csv.DictReader(path.open(encoding="utf-8")))
    assert list(rows[0]) == corrections_log.COLUMNS
    assert [(r["field"], r["value_read"], r["value_confirmed"], r["action"]) for r in rows] == [
        ("brand", "Lo", "LG", "corrected"),
        ("model_code", "OLEDSS-002", "OLEDSS-002", "confirmed"),
        ("serial_no", "SNO01X1001", "", "dismissed"),
        ("product_name", "", "Call [REDACTED] OLED TV", "entered"),
        ("purchase_date", "", "2025-01-11", "entered"),
    ]
    assert "9876543210" not in path.read_text(encoding="utf-8") and "wty_corr_on" not in path.read_text(encoding="utf-8")


def test_default_location_is_git_ignored():
    import subprocess
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    rel = corrections_log._DEFAULT_PATH.relative_to(root).as_posix()
    assert rel == "real_invoices/corrections.csv"
    assert subprocess.run(["git", "check-ignore", "-q", rel], cwd=root).returncode == 0
