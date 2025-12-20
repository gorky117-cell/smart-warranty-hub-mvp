import requests
import json

BASE = "http://127.0.0.1:8000"


def main():
    r = requests.post(
        f"{BASE}/auth/login",
        data={"username": "admin", "password": "admin123"},
        headers={"accept": "application/json"},
    )
    r.raise_for_status()
    token = r.json().get("access_token")
    headers = {"Authorization": f"Bearer {token}", "accept": "application/json"}

    # missing warranty_id
    resp = requests.get(f"{BASE}/behaviour/next-question", params={"user_id": "user-1"}, headers=headers)
    print("missing warranty_id status", resp.status_code)
    print(resp.json())

    # proper request
    resp2 = requests.get(
        f"{BASE}/behaviour/next-question",
        params={"user_id": "user-1", "warranty_id": "wty_55f018de"},
        headers=headers,
    )
    print("valid status", resp2.status_code)
    print(json.dumps(resp2.json(), indent=2))


if __name__ == "__main__":
    main()
