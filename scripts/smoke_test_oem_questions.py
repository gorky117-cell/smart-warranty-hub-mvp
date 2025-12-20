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
    print("API_BASE candidates: /oem, /api/oem")
    llm = get("/oem/questions/llm-status", headers)
    print("llm-status", llm.status_code, llm.text)
    llm.raise_for_status()
    gen = post("/oem/questions/generate", headers=headers, json={"brand": "Acmeco", "model": "ZX-100"})
    print("generate", gen.status_code, gen.text)
    gen.raise_for_status()
    data = gen.json()
    assert data.get("ok") is True
    qs = data.get("questions") or [{"text": "Fallback?", "answer_type": "text"}]
    pub = post("/oem/questions/publish", headers=headers, json={"brand": "Acmeco", "model": "ZX-100", "question": qs[0]})
    print("publish", pub.status_code, pub.text)
    pub.raise_for_status()
    qid = pub.json().get("question_id") or pub.json().get("id")
    act = get("/oem/questions/active", headers, params={"brand": "Acmeco", "model": "ZX-100"})
    print("active", act.status_code, json.dumps(act.json(), indent=2))
    act.raise_for_status()
    if qid:
        dis = post("/oem/questions/disable", headers=headers, json={"question_id": qid})
        print("disable", dis.status_code, dis.text)
        dis.raise_for_status()


if __name__ == "__main__":
    main()
