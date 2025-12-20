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
    return {"Authorization": f"Bearer {token}", "accept": "application/json", "Content-Type": "application/json"}


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
    # generate (fallback, ENABLE_LLM_QUESTIONS=0 assumed)
    gen = post_with_fallback(
        "/oem/questions/generate",
        headers=headers,
        json={"brand": "Acmeco", "model_code": "ZX-100", "region": "NA", "n": 2},
    )
    print("generate", gen.status_code)
    print(gen.json())
    gen.raise_for_status()
    assert gen.json().get("ok") is True
    # publish first two
    data = gen.json()
    qs = data.get("questions") or []
    first_q = (qs or [{"text": "Is device indoors?", "answer_type": "choice", "options": ["Yes", "No"]}])[0]
    pub = post_with_fallback(
        "/oem/questions/publish",
        headers=headers,
        json={"brand": "Acmeco", "model_code": "ZX-100", "region": "NA", "question": first_q},
    )
    print("publish", pub.status_code, pub.json())
    pub.raise_for_status()
    assert pub.json().get("ok") is True
    qid = pub.json().get("question_id")
    # active
    act = get_with_fallback("/oem/questions/active", headers=headers, params={"brand": "Acmeco", "model_code": "ZX-100"})
    print("active", act.status_code)
    print(json.dumps(act.json(), indent=2))
    act.raise_for_status()
    assert act.json().get("ok") is True
    # disable
    if qid:
        dis = post_with_fallback(
            "/oem/questions/disable",
            headers=headers,
            json={"question_id": qid},
        )
        print("disable", dis.status_code, dis.text)
        dis.raise_for_status()


if __name__ == "__main__":
    main()
