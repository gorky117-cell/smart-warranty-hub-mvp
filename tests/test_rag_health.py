from app.db import SessionLocal
from app.services import rag


def test_rag_health_payload_shape():
    with SessionLocal() as db:
        out = rag.health(db)
    assert isinstance(out, dict)
    assert "enabled_env" in out
    assert "api_key_present" in out
    assert "active" in out
    assert "ok" in out


def test_rag_smoke_disabled_path(monkeypatch):
    monkeypatch.setattr(rag, "_RAG_ENABLED", False)
    monkeypatch.setattr(rag, "_MISTRAL_KEY", None)
    with SessionLocal() as db:
        out = rag.smoke_test(db)
    assert out["ok"] is False
    assert out["detail"] == "rag_disabled_or_missing_api_key"
    assert out["embed_ok"] is False
    assert out["retrieval_ok"] is False
