import requests
import json

BASE = "http://127.0.0.1:8000"
USER = "admin"
PASS = "admin123"


def login():
    resp = requests.post(f"{BASE}/auth/login", data={"username": USER, "password": PASS}, headers={"accept": "application/json"})
    resp.raise_for_status()
    token = resp.json().get("access_token")
    return {"Authorization": f"Bearer {token}", "accept": "application/json"}


def main():
    headers = login()
    resp = requests.get(
        f"{BASE}/behaviour/next-question",
        params={"user_id": "user-1", "warranty_id": "wty_55f018de"},
        headers=headers,
    )
    print("status", resp.status_code)
    resp.raise_for_status()
    data = resp.json()
    print(json.dumps(data, indent=2))


if __name__ == "__main__":
    main()
