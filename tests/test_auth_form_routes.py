from fastapi.testclient import TestClient

from app.main import app


def test_get_signup_form_redirects_to_login():
    client = TestClient(app)

    resp = client.get("/auth/signup/form", follow_redirects=False)

    assert resp.status_code == 303
    assert resp.headers["location"] == "/login"
