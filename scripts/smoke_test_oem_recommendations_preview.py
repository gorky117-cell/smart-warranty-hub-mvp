import requests
import json

BASE = "http://127.0.0.1:8000"


def login():
    r = requests.post(
        f"{BASE}/auth/login",
        data={"username": "admin", "password": "admin123"},
        headers={"accept": "application/json"},
    )
    r.raise_for_status()
    token = r.json().get("access_token")
    return {"Authorization": f"Bearer {token}", "accept": "application/json"}


def main():
    headers = login()
    r = requests.get(f"{BASE}/oem/recommendations/preview", headers=headers, params={"brand": "Acmeco", "model": "ZX-100"})
    if r.status_code == 404:
        r = requests.get(f"{BASE}/api/oem/recommendations/preview", headers=headers, params={"brand": "Acmeco", "model": "ZX-100"})
    print("preview status", r.status_code)
    r.raise_for_status()
    data = r.json()
    print(json.dumps(data, indent=2))
    assert data.get("ok") is True
    for key in ["risk_distribution", "top_risks", "likely_user_needs", "suggested_oem_actions", "suggested_products", "recommendation_message"]:
        assert key in data, f"missing {key}"


if __name__ == "__main__":
    main()
