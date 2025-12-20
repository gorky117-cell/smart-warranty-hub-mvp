import requests
import json
import os

BASE = os.getenv("BASE_URL", "http://127.0.0.1:8000")


def login():
    r = requests.post(
        f"{BASE}/auth/login",
        data={"username": "admin", "password": "admin123"},
        headers={"accept": "application/json"},
    )
    r.raise_for_status()
    token = r.json().get("access_token")
    return {"Authorization": f"Bearer {token}", "accept": "application/json", "Content-Type": "application/json"}


def get(path, headers, **kw):
    r = requests.get(f"{BASE}{path}", headers=headers, **kw)
    if r.status_code == 404:
        r = requests.get(f"{BASE}/api{path}", headers=headers, **kw)
    return r


def post(path, headers, **kw):
    r = requests.post(f"{BASE}{path}", headers=headers, **kw)
    if r.status_code == 404:
        r = requests.post(f"{BASE}/api{path}", headers=headers, **kw)
    return r


def main():
    headers = login()
    preview = get("/oem/recommendations/preview", headers, params={"brand": "Acmeco", "model": "ZX-100"})
    print("preview", preview.status_code, json.dumps(preview.json(), indent=2))
    preview.raise_for_status()
    gen = post("/oem/recommendations/generate", headers=headers, json={"brand": "Acmeco", "model": "ZX-100"})
    print("generate", gen.status_code, gen.text)
    gen.raise_for_status()
    data = gen.json()
    assert data.get("ok") is True
    recs = data.get("recommendations") or []
    first = recs[0] if recs else {"title": "Test rec", "message": "Hello"}
    pub = post("/oem/recommendations/publish", headers=headers, json={"recommendation": first})
    print("publish", pub.status_code, pub.text)
    pub.raise_for_status()
    rec_id = pub.json().get("id")
    act = get("/oem/recommendations/active", headers, params={"brand": "Acmeco"})
    print("active", act.status_code, json.dumps(act.json(), indent=2))
    act.raise_for_status()
    if rec_id:
        dis = post("/oem/recommendations/disable", headers=headers, json={"id": rec_id})
        print("disable", dis.status_code, dis.text)
        dis.raise_for_status()


if __name__ == "__main__":
    main()
