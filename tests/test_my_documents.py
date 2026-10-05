"""Customer experience step 2: My documents - owner-only view, download and delete of originals."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.db import SessionLocal
from app.db_models import DocumentDB, UserDB, WarrantyDB, WarrantyOwnerDB
from app.deps import hash_password
from app.main import app
from app.services import document_store

OWNER, OTHER = "docs_owner_user", "docs_other_user"
# A mix of product types and brands (global rule): the feature must not depend on the product.
PRODUCTS = {
    "wty_doc_phone": ("Samsung", "Galaxy M17e", "SM-M175F"),
    "wty_doc_fridge": ("LG", "Refrigerator", "GL-T292RPZY"),
    "wty_doc_ac": ("Voltas", "Split AC", "183V"),
    "wty_doc_printer": ("Epson", "EcoTank L3250", "L3250"),
}
FILES = {  # kind -> (filename, bytes, content type): text PDF, scanned card, phone photo, text file
    "invoice": ("Tax_Invoice.pdf", b"%PDF-1.4 test invoice", "application/pdf"),
    "warranty_card": ("card.jpg", b"\xff\xd8\xff\xe0 jpeg card", "image/jpeg"),
    "photo": ("IMG_2041.png", b"\x89PNG\r\n photo", "image/png"),
    "other": ("notes.txt", b"bought at the local shop", "text/plain"),
}


def _reset():
    with SessionLocal() as db:
        db.query(DocumentDB).filter(DocumentDB.owner_user_id.in_([OWNER, OTHER])).delete(synchronize_session=False)
        db.query(WarrantyOwnerDB).filter(WarrantyOwnerDB.user_id.in_([OWNER, OTHER])).delete(synchronize_session=False)
        db.query(WarrantyDB).filter(WarrantyDB.id.like("wty_doc_%")).delete(synchronize_session=False)
        from app.db_models import PipelineJobDB

        db.query(PipelineJobDB).filter(PipelineJobDB.warranty_id.like("wty_doc_%")).delete(synchronize_session=False)
        for name in (OWNER, OTHER):
            if not db.query(UserDB).filter_by(username=name).first():
                db.add(UserDB(username=name, role="user", hashed_password=hash_password("secret123")))
        for wid, (brand, name, model) in PRODUCTS.items():
            db.add(WarrantyDB(id=wid, brand=brand, product_name=name, model_code=model, alternatives={}))
            db.add(WarrantyOwnerDB(user_id=OWNER, warranty_id=wid))
        db.commit()


def _client(user):
    client = TestClient(app)
    token = client.post("/auth/login", data={"username": user, "password": "secret123" if user != "admin" else "admin123"},
                        headers={"accept": "application/json"}).json()["access_token"]
    return client, {"Authorization": f"Bearer {token}"}


@pytest.fixture(autouse=True)
def _fresh(monkeypatch):
    monkeypatch.setenv("RATE_LIMIT_ENABLED", "0")
    _reset()


@pytest.mark.parametrize("backend", ["local", "db"])
def test_owner_adds_lists_views_downloads_and_deletes(monkeypatch, backend):
    monkeypatch.setenv("DOCUMENT_STORE", backend)
    client, auth = _client(OWNER)
    for wid in PRODUCTS:
        for kind, (name, data, ctype) in FILES.items():
            resp = client.post(f"/warranties/{wid}/documents", files={"file": (name, data, ctype)}, data={"kind": kind}, headers=auth)
            assert resp.status_code == 200, resp.text
        listed = client.get(f"/warranties/{wid}/documents", headers=auth).json()["documents"]
        assert {d["kind"] for d in listed} == set(FILES)
        for doc in listed:
            assert doc["uploaded_at"] and doc["kind_label"] and doc["available"]
            assert "location" not in doc and "owner_user_id" not in doc  # no storage paths or owner shown
            name, data, _ = FILES[doc["kind"]]
            view = client.get(f"/documents/{doc['id']}/file", headers=auth)
            assert view.status_code == 200 and view.content == data
            assert view.headers["content-disposition"].startswith("inline")
            dl = client.get(f"/documents/{doc['id']}/file?download=1", headers=auth)
            assert dl.headers["content-disposition"].startswith("attachment") and name in dl.headers["content-disposition"]
        first = listed[0]["id"]
        assert client.delete(f"/documents/{first}", headers=auth).status_code == 200
        assert client.get(f"/documents/{first}/file", headers=auth).status_code == 404
        assert len(client.get(f"/warranties/{wid}/documents", headers=auth).json()["documents"]) == len(FILES) - 1
    with SessionLocal() as db:
        stored = db.query(DocumentDB).filter_by(owner_user_id=OWNER).all()
        assert {d.storage for d in stored} == {backend}


def test_other_users_and_staff_accounts_are_denied():
    owner, auth = _client(OWNER)
    doc = owner.post("/warranties/wty_doc_phone/documents", files={"file": FILES["invoice"]}, data={"kind": "invoice"}, headers=auth).json()
    for user in (OTHER, "admin"):  # owner-only, also for admin accounts
        client, other_auth = _client(user)
        assert client.get("/warranties/wty_doc_phone/documents", headers=other_auth).status_code == 404
        assert client.get(f"/documents/{doc['id']}/file", headers=other_auth).status_code == 404
        assert client.delete(f"/documents/{doc['id']}", headers=other_auth).status_code == 404
        assert client.post("/warranties/wty_doc_phone/documents", files={"file": FILES["photo"]}, data={"kind": "photo"},
                           headers=other_auth).status_code == 404
    assert owner.get(f"/documents/{doc['id']}/file", headers=auth).status_code == 200  # still there


def test_same_file_twice_is_stored_once_and_bad_types_are_refused():
    client, auth = _client(OWNER)
    for _ in range(2):
        client.post("/warranties/wty_doc_ac/documents", files={"file": FILES["invoice"]}, data={"kind": "invoice"}, headers=auth)
    assert len(client.get("/warranties/wty_doc_ac/documents", headers=auth).json()["documents"]) == 1
    bad = client.post("/warranties/wty_doc_ac/documents", files={"file": ("x.exe", b"MZ", "application/octet-stream")}, headers=auth)
    assert bad.status_code == 415


def test_missing_original_is_reported_not_crashing(monkeypatch):
    monkeypatch.setenv("DOCUMENT_STORE", "local")
    client, auth = _client(OWNER)
    doc = client.post("/warranties/wty_doc_fridge/documents", files={"file": FILES["invoice"]}, data={"kind": "invoice"}, headers=auth).json()
    with SessionLocal() as db:  # what a redeploy without a volume does to a local file
        Path(db.query(DocumentDB).filter_by(id=doc["id"]).first().location).unlink()
    listed = client.get("/warranties/wty_doc_fridge/documents", headers=auth).json()["documents"]
    assert listed[0]["available"] is False
    assert client.get(f"/documents/{doc['id']}/file", headers=auth).status_code == 410


def test_invoice_upload_keeps_the_original(monkeypatch):
    monkeypatch.setenv("DOCUMENT_STORE", "db")
    client, auth = _client(OWNER)
    bill = b"Tax Invoice\n1 Epson L3250 Printer\nInvoice Date 01-05-2026"
    resp = client.post("/artifacts/upload", files={"file": ("bill.txt", bill, "text/plain")}, data={"type": "invoice"}, headers=auth)
    assert resp.status_code == 200
    docs = client.get(f"/warranties/{resp.json()['warranty_id']}/documents", headers=auth).json()["documents"]
    assert [d["kind"] for d in docs] == ["invoice"] and docs[0]["filename"] == "bill.txt"


def test_kind_follows_the_upload_type():
    assert document_store.kind_for_artifact("invoice", ".jpg") == "invoice"
    assert document_store.kind_for_artifact("label", ".pdf") == "warranty_card"
    assert document_store.kind_for_artifact("other", ".jpeg") == "photo"
    assert document_store.kind_for_artifact("other", ".pdf") == "other"


def test_dashboard_has_my_documents_with_dropdown_and_owner_note(monkeypatch):
    client, _ = _client(OWNER)
    client.post("/auth/login", data={"username": OWNER, "password": "secret123"})
    html = client.get("/ui/neo-dashboard").text
    assert '<summary>My documents</summary>' in html and "Only you can see them." in html
    assert '<select id="docKind"' in html and 'value="warranty_card"' in html  # a dropdown, not free text
    assert "loadDocuments(warrantyId);" in html  # refreshed whenever a product loads
    assert "File no longer available - please upload again." in html


def test_files_are_kept_in_the_database_by_default(monkeypatch):
    monkeypatch.delenv("DOCUMENT_STORE", raising=False)
    assert document_store.backend() == "db"
    monkeypatch.setenv("DOCUMENT_STORE", "nonsense")
    assert document_store.backend() == "db"
    monkeypatch.setenv("DOCUMENT_STORE", "local")  # disk only when set explicitly
    assert document_store.backend() == "local"
    monkeypatch.delenv("DOCUMENT_STORE", raising=False)
    client, auth = _client(OWNER)
    doc = client.post("/warranties/wty_doc_printer/documents", files={"file": FILES["photo"]}, data={"kind": "photo"}, headers=auth).json()
    with SessionLocal() as db:
        row = db.query(DocumentDB).filter_by(id=doc["id"]).one()
        assert row.storage == "db" and row.data == FILES["photo"][1] and row.location is None


def _old_upload_job(wid, path):
    from datetime import datetime

    from app.db_models import PipelineJobDB

    with SessionLocal() as db:
        db.query(PipelineJobDB).filter_by(warranty_id=wid).delete()
        db.add(PipelineJobDB(id=f"job_{wid}", warranty_id=wid, source_path=str(path), status="done",
                             created_at=datetime(2026, 5, 2, 10, 30)))
        db.commit()


def test_old_upload_gone_says_upload_again(tmp_path, monkeypatch):
    monkeypatch.delenv("DOCUMENT_STORE", raising=False)
    _old_upload_job("wty_doc_phone", tmp_path / "upload_gone.pdf")  # the file was lost in a redeploy
    client, auth = _client(OWNER)
    docs = client.get("/warranties/wty_doc_phone/documents", headers=auth).json()["documents"]
    assert docs == [{**docs[0], "id": None, "kind": "invoice", "available": False, "missing_upload": True}]
    assert docs[0]["uploaded_at"].startswith("2026-05-02")
    other, other_auth = _client(OTHER)
    assert other.get("/warranties/wty_doc_phone/documents", headers=other_auth).status_code == 404


def test_old_upload_still_on_disk_is_saved_to_the_database(tmp_path, monkeypatch):
    monkeypatch.delenv("DOCUMENT_STORE", raising=False)
    old = tmp_path / "upload_still_here.pdf"
    old.write_bytes(b"%PDF-1.4 old invoice")
    _old_upload_job("wty_doc_fridge", old)
    client, auth = _client(OWNER)
    docs = client.get("/warranties/wty_doc_fridge/documents", headers=auth).json()["documents"]
    assert len(docs) == 1 and docs[0]["available"] and docs[0]["kind"] == "invoice"
    old.unlink()  # a later redeploy: the copy in the database still opens
    assert client.get(f"/documents/{docs[0]['id']}/file", headers=auth).content == b"%PDF-1.4 old invoice"
