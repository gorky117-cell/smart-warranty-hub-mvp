import requests
import json

BASE = "http://127.0.0.1:8000"
USER = "admin"
PASS = "admin123"
TARGET_USER = "user-1"
TARGET_WARRANTY = "wty_55f018de"


def login():
    r = requests.post(f"{BASE}/auth/login", data={"username": USER, "password": PASS}, headers={"accept": "application/json"})
    r.raise_for_status()
    return {"Authorization": f"Bearer {r.json().get('access_token')}", "accept": "application/json", "Content-Type": "application/json"}


def main():
    headers = login()
    def post_with_fallback(path, **kw):
        r = requests.post(f"{BASE}{path}", **kw)
        if r.status_code == 404:
            r = requests.post(f"{BASE}/api{path}", **kw)
        return r
    def get_with_fallback(path, **kw):
        r = requests.get(f"{BASE}{path}", **kw)
        if r.status_code == 404:
            r = requests.get(f"{BASE}/api{path}", **kw)
        return r
    # publish one OEM question
    q = {"text": "Is this used mostly indoors?", "answer_type": "choice", "options": ["Home", "Office", "Outdoor", "Mixed"], "enabled": True}
    pub = post_with_fallback(
        "/oem/questions/publish",
        headers=headers,
        json={"brand": "Acmeco", "model_code": "ZX-100", "question": q},
    )
    print("publish status", pub.status_code)
    pub.raise_for_status()
    assert pub.json().get("ok") is True
    # fetch next-question
    nxt = get_with_fallback(
        "/behaviour/next-question",
        headers=headers,
        params={"user_id": TARGET_USER, "warranty_id": TARGET_WARRANTY},
    )
    print("next status", nxt.status_code)
    nxt.raise_for_status()
    data = nxt.json()
    print(json.dumps(data, indent=2))
    assert data.get("reason", "").startswith("oem"), "OEM question not served first"
    qid = data.get("question_id") or (data.get("question") or {}).get("id")
    # answer
    ans = post_with_fallback(
        "/behaviour/answer",
        headers=headers,
        json={"user_id": TARGET_USER, "warranty_id": TARGET_WARRANTY, "question_id": qid, "answer_value": "Yes"},
    )
    print("answer status", ans.status_code, ans.text)
    ans.raise_for_status()
    # next again
    nxt2 = get_with_fallback(
        "/behaviour/next-question",
        headers=headers,
        params={"user_id": TARGET_USER, "warranty_id": TARGET_WARRANTY},
    )
    print("next2", nxt2.status_code, nxt2.text)
    nxt2.raise_for_status()


if __name__ == "__main__":
    main()
