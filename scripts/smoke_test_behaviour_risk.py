"""
Quick smoke test to verify behaviour/telemetry now influences predictive risk.
Runs two telemetry scenarios (good vs bad) for a sample warranty and checks
that the predictive label/score changes.
"""
import json
import sys
import requests

BASE = "http://127.0.0.1:8000"
ADMIN_USER = "admin"
ADMIN_PASS = "admin123"
SAMPLE_USER_ID = "user-1"
SAMPLE_WARRANTY_ID = "wty_55f018de"


def pretty(label, resp):
    print(f"\n=== {label} ===")
    print("STATUS:", resp.status_code)
    try:
        data = resp.json()
        print("JSON:", json.dumps(data, indent=2)[:400])
    except Exception:
        print("RAW:", resp.text[:400])


def login():
    resp = requests.post(
        f"{BASE}/auth/login",
        data={"username": ADMIN_USER, "password": ADMIN_PASS},
        headers={"accept": "application/json"},
    )
    pretty("LOGIN", resp)
    resp.raise_for_status()
    token = resp.json().get("access_token")
    if not token:
        sys.exit("No token returned from login.")
    return {"Authorization": f"Bearer {token}"}


def load_warranty(headers):
    resp = requests.get(
        f"{BASE}/warranties/{SAMPLE_WARRANTY_ID}",
        headers={**headers, "Accept": "application/json"},
    )
    pretty("LOAD WARRANTY", resp)
    resp.raise_for_status()


def send_telemetry(headers, hours: float, errors: int):
    payload = {"hours": hours, "errors": errors, "region": "APAC"}
    load_warranty(headers)  # ensure cache is populated even after reloads
    resp = requests.post(
        f"{BASE}/telemetry",
        headers={**headers, "Content-Type": "application/json"},
        json={
            "user_id": SAMPLE_USER_ID,
            "warranty_id": SAMPLE_WARRANTY_ID,
            "event_type": "usage",
            "payload": payload,
        },
    )
    pretty(f"TELEMETRY hours={hours} errors={errors}", resp)
    resp.raise_for_status()


def fetch_predictive(headers, label):
    resp = requests.post(
        f"{BASE}/predictive/score",
        headers={**headers, "Content-Type": "application/json"},
        json={"user_id": SAMPLE_USER_ID, "warranty_id": SAMPLE_WARRANTY_ID},
    )
    pretty(label, resp)
    resp.raise_for_status()
    data = resp.json()
    return data.get("risk_label"), float(data.get("risk_score", 0.0)), data.get("reasons", [])


def main():
    headers = login()

    # Good behaviour: low hours, no errors
    send_telemetry(headers, hours=2, errors=0)
    label_good, score_good, reasons_good = fetch_predictive(headers, "PREDICTIVE good")

    # Bad behaviour: heavy usage and multiple errors
    send_telemetry(headers, hours=2500, errors=8)
    label_bad, score_bad, reasons_bad = fetch_predictive(headers, "PREDICTIVE bad")

    print("\n=== SUMMARY ===")
    print("Good:", label_good, score_good, reasons_good[:3])
    print("Bad :", label_bad, score_bad, reasons_bad[:3])

    if label_bad != label_good or score_bad > score_good:
        print("PASS: Behaviour impacts predictive risk.")
    else:
        sys.exit("FAIL: Behaviour did not change predictive risk.")


if __name__ == "__main__":
    main()
