import requests
import json

BASE = "http://127.0.0.1:8000"
USER = "admin"
PASS = "admin123"
TARGET_USER = "user-1"
TARGET_WARRANTY = "wty_55f018de"


def login():
    resp = requests.post(f"{BASE}/auth/login", data={"username": USER, "password": PASS}, headers={"accept": "application/json"})
    resp.raise_for_status()
    token = resp.json().get("access_token")
    return {"Authorization": f"Bearer {token}", "accept": "application/json", "Content-Type": "application/json"}


def main():
    headers = login()
    # fetch first question
    r1 = requests.get(f"{BASE}/behaviour/next-question", params={"user_id": TARGET_USER, "warranty_id": TARGET_WARRANTY}, headers=headers)
    print("next-question status", r1.status_code)
    r1.raise_for_status()
    q = r1.json()
    print("first:", json.dumps(q, indent=2))
    if q.get("question") is None:
        print("No question available; done=True")
        return
    qid = q.get("question_id") or q["question"]["id"]
    # answer with first option if present
    answer_val = None
    opts = q["question"].get("options") if q.get("question") else None
    if opts:
        answer_val = opts[0]
    else:
        answer_val = "yes"
    r2 = requests.post(
        f"{BASE}/behaviour/answer",
        headers=headers,
        json={"user_id": TARGET_USER, "warranty_id": TARGET_WARRANTY, "product_type": None, "question_id": qid, "answer_value": answer_val},
    )
    print("answer status", r2.status_code, r2.text)
    r2.raise_for_status()
    # fetch next question
    r3 = requests.get(f"{BASE}/behaviour/next-question", params={"user_id": TARGET_USER, "warranty_id": TARGET_WARRANTY}, headers=headers)
    print("next-question after answer", r3.status_code)
    r3.raise_for_status()
    print("second:", json.dumps(r3.json(), indent=2))


if __name__ == "__main__":
    main()
