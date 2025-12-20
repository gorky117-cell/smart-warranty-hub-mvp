import requests
import json

BASE_URL = "http://127.0.0.1:8000"


def main():
    resp = requests.post(
        f"{BASE_URL}/auth/login",
        data={"username": "admin", "password": "admin123"},
        headers={"accept": "application/json"},
    )
    resp.raise_for_status()
    token = resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}", "accept": "application/json"}

    r = requests.get(
        f"{BASE_URL}/recommendations",
        headers=headers,
        params={"user_id": "user-1", "warranty_id": "wty_55f018de"},
    )
    print("STATUS", r.status_code)
    r.raise_for_status()
    data = r.json()
    prs = data.get("product_recommendations") if isinstance(data, dict) else None
    print("product_recommendations type:", type(prs))
    if isinstance(prs, list):
        print("count:", len(prs))
        if prs:
            print("first:", json.dumps(prs[0], indent=2))
    else:
        print("No list found for product_recommendations")


if __name__ == "__main__":
    main()
