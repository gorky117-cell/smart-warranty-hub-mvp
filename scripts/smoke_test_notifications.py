import json
import requests

BASE = "http://127.0.0.1:8000"

ADMIN_USER = "admin"
ADMIN_PASS = "admin123"

SAMPLE_USER_ID = "user-1"
SAMPLE_WARRANTY_ID = "wty_55f018de"  # adjust if different in DB


def pretty(label, resp):
    print(f"\n=== {label} ===")
    print("STATUS:", resp.status_code)
    try:
        data = resp.json()
        print("JSON:", json.dumps(data, indent=2)[:400])
    except Exception:
        text = resp.text
        print("RAW:", text[:400])


def main():
    resp = requests.post(
        f"{BASE}/auth/login",
        data={"username": ADMIN_USER, "password": ADMIN_PASS},
        headers={"accept": "application/json"},
    )
    pretty("LOGIN", resp)
    resp.raise_for_status()
    token = resp.json().get("access_token")
    if not token:
        print("No token in login response, aborting.")
        return

    headers = {"Authorization": f"Bearer {token}"}

    r_health = requests.get(f"{BASE}/health/full", headers=headers)
    pretty("HEALTH /health/full", r_health)

    r_oem_stats = requests.get(f"{BASE}/oem/risk-stats", headers=headers)
    pretty("OEM RISK-STATS /oem/risk-stats", r_oem_stats)

    r_oem_notifs = requests.get(
        f"{BASE}/oem/notifications",
        headers=headers,
        params={"only_unread": "true"},
    )
    pretty("OEM NOTIFICATIONS /oem/notifications", r_oem_notifs)

    r_user_notifs = requests.get(
        f"{BASE}/notifications",
        headers=headers,
        params={"user_id": SAMPLE_USER_ID, "only_unread": "true"},
    )
    pretty("USER NOTIFICATIONS /notifications", r_user_notifs)

    r_adv = requests.get(
        f"{BASE}/advisories/{SAMPLE_WARRANTY_ID}",
        headers=headers,
        params={"user_id": SAMPLE_USER_ID},
    )
    pretty(f"ADVISORIES /advisories/{SAMPLE_WARRANTY_ID}", r_adv)


if __name__ == "__main__":
    main()
