"""Run 3 item 6: customer text in plain words; technical detail admin-only; pickers instead of free text."""

import re
from datetime import datetime
from html.parser import HTMLParser

import pytest
from fastapi.testclient import TestClient

from app.db import SessionLocal
from app.db_models import NotificationDB, UserDB, WarrantyDB, WarrantyOwnerDB
from app.deps import hash_password
from app.main import app
from app.services import behaviour_questions, notifications as ns
from app.services.source_trust import classify_terms_source
from app.services.summary_engine import build_evidence_summary

USER = "plain_words_user"
# Internal terms a customer must never read.
JARGON = re.compile(
    r"\b(OEM|variant|base score|delta|baseline|canonical|pipeline|artifact|telemetry|payload|JSON|"
    r"risk score|confidence|heuristic|fixture|cache|wty_[a-z0-9]+|OCR|extraction|Pred)\b",
    re.IGNORECASE,
)
VOID = {"input", "br", "img", "hr", "meta", "link", "source", "wbr", "option"}


class _Visible(HTMLParser):
    """Static text a customer sees: no scripts/styles, nothing inside an admin-only element."""

    def __init__(self):
        super().__init__()
        self.stack, self.text = [], []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        hidden = "admin-only" in (attrs.get("class") or "").split() or tag in ("script", "style", "title")
        if tag == "input" and attrs.get("placeholder") and not self._hidden():
            self.text.append(attrs["placeholder"])
        if tag not in VOID:
            self.stack.append((tag, hidden))

    def handle_endtag(self, tag):
        while self.stack and self.stack.pop()[0] != tag:
            pass

    def _hidden(self):
        return any(h for _, h in self.stack)

    def handle_data(self, data):
        if data.strip() and not self._hidden():
            self.text.append(" ".join(data.split()))


def _user():
    with SessionLocal() as db:
        if not db.query(UserDB).filter_by(username=USER).first():
            db.add(UserDB(username=USER, role="user", hashed_password=hash_password("secret123")))
            db.commit()


def _page(user=USER, password="secret123"):
    client = TestClient(app)
    client.post("/auth/login", data={"username": user, "password": password})
    return client.get("/ui/neo-dashboard").text


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    monkeypatch.setenv("RATE_LIMIT_ENABLED", "0")
    _user()


def test_customer_page_visible_text_has_no_internal_terms():
    parser = _Visible()
    parser.feed(_page())
    # DEV tools sit in a block the page shows only with ?dev=1 for testers; everything else is checked.
    found = sorted({m.group(0) for line in parser.text if "DEV" not in line and "telemetry" not in line.lower()
                    for m in JARGON.finditer(line)})
    assert found == []


def test_technical_controls_are_admin_only():
    html = _page()
    for marker in ('id="hb-ocr"', 'id="rawWarrantyToggle"', 'class="toggle advanced-toggle', 'id="oemModal"'):
        tag = html[html.index(marker) - 200: html.index(marker) + 120]
        assert "admin-only" in tag, marker
    assert "IS_ADMIN ? `Uploaded, but extraction needs review" in html  # raw job errors only for admin


@pytest.mark.parametrize("source_type,url", [
    ("default_rules", None), ("invoice_only", None), ("internal_terms_cache", None),
    ("internal_warranty_db", None), (None, None), ("scraped", "https://example-reviews.com/x"),
])
def test_where_terms_came_from_is_plain(source_type, url):
    class W:
        brand, product_name, model_code, id = "Acmeco", "Mixer Grinder", "MG-1", "wty_x"
        alternatives = {"terms_source_type": source_type, "terms_source_url": url} if source_type else {}
        terms_source_url = url

    evidence = build_evidence_summary(W())
    text = f"{evidence['status_label']} {evidence['note']}"
    assert not JARGON.search(text), text
    trust = classify_terms_source(brand="Acmeco", source_url=url, source_type=source_type)
    assert not JARGON.search(f"{trust['label']} {trust['note']}")


def test_estimated_terms_say_estimated_please_check():
    trust = classify_terms_source(brand="Unknownco", source_url=None, source_type="default_rules")
    assert trust["label"] == "Estimated, please check"


def test_questions_name_the_brand_terms_not_the_oem_source():
    import inspect

    assert "OEM source" not in inspect.getsource(behaviour_questions)


def test_notifications_name_the_product_never_the_id():
    with SessionLocal() as db:
        db.query(NotificationDB).filter_by(user_id=USER).delete()
        db.query(WarrantyDB).filter_by(id="wty_pl_1").delete()
        db.add(WarrantyDB(id="wty_pl_1", brand="Samsung", product_name="Samsung Galaxy M17e 5G (Blue, 6GB RAM)",
                          model_code="SM-M175F", purchase_date=datetime(2026, 5, 1), alternatives={}))
        db.add(NotificationDB(id="ntf_pl_old", user_id=USER, warranty_id="wty_pl_1", type="legacy", title="Warranty wty_pl_1",
                              message="Your warranty wty_pl_1 ends soon.", severity="info", is_read=0,
                              created_at=datetime.utcnow(), audience="user"))
        db.commit()
        items = ns.list_notifications(USER, db=db)
    item = next(i for i in items if i["id"] == "ntf_pl_old")
    assert item["product_label"] == "Samsung Galaxy M17e 5G"
    assert "wty_" not in item["title"] + item["message"]


def test_pickers_instead_of_free_text():
    html = _page()
    assert 'list="brandOptions"' in html and '<option value="Samsung">' in html and "__SWH_BRAND_OPTIONS__" not in html
    assert '<input id="mAmount" type="number"' in html
    assert 'id="telType" onchange="syncNoteInput()"' in html and 'id="telPayloadSimple" type="number"' in html
    assert '<option value="label">Warranty card or label</option>' in html
