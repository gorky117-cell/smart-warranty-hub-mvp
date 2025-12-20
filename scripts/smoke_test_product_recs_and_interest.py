import json
import requests

BASE_URL = "http://127.0.0.1:8000"
ADMIN_USER = "admin"
ADMIN_PASS = "admin123"


def pretty(label, resp):
    print(f"\n=== {label} ===")
    print("STATUS", resp.status_code)
    try:
        data = resp.json()
        print(json.dumps(data, indent=2)[:400])
    except Exception:
        print(resp.text[:400])


def main():
    # login
    r = requests.post(
        f"{BASE_URL}/auth/login",
        data={"username": ADMIN_USER, "password": ADMIN_PASS},
        headers={"accept": "application/json"},
    )
    pretty("LOGIN", r)
    r.raise_for_status()
    token = r.json().get("access_token")
    headers = {"Authorization": f"Bearer {token}", "accept": "application/json"}

    # recommendations (should contain product_recommendations)
    rec = requests.get(
        f"{BASE_URL}/recommendations",
        headers=headers,
        params={"user_id": "user-1", "warranty_id": "wty_55f018de"},
    )
    pretty("RECOMMENDATIONS", rec)
    rec.raise_for_status()
    data = rec.json()
    assert "product_recommendations" in data, "product_recommendations missing"
    assert isinstance(data.get("product_recommendations"), list), "product_recommendations not a list"

    # post one product-interest event
    pei = requests.post(
        f"{BASE_URL}/events/product-interest",
        headers={**headers, "Content-Type": "application/json"},
        json={
            "user_id": "user-1",
            "warranty_id": "wty_55f018de",
            "region": "APAC",
            "product_id": "sp_ultra",
            "action": "view",
        },
    )
    pretty("PRODUCT INTEREST", pei)
    pei.raise_for_status()


if __name__ == "__main__":
    main()
