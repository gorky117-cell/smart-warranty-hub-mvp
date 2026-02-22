from __future__ import annotations

import math
import os
from typing import List, Dict, Optional, Tuple, Iterable

import requests
from sqlalchemy.orm import Session

from ..db_models import DocumentEmbeddingDB


_MISTRAL_API = os.getenv("MISTRAL_API_URL", "https://api.mistral.ai/v1")
_MISTRAL_KEY = os.getenv("MISTRAL_API_KEY")
_EMBED_MODEL = os.getenv("MISTRAL_EMBED_MODEL", "mistral-embed")
_RAG_ENABLED = os.getenv("RAG_ENABLED", "0").strip().lower() in ("1", "true", "yes")


def rag_enabled() -> bool:
    return _RAG_ENABLED and bool(_MISTRAL_KEY)


def _embed(text: str) -> Optional[List[float]]:
    if not _MISTRAL_KEY:
        return None
    try:
        resp = requests.post(
            f"{_MISTRAL_API.rstrip('/')}/embeddings",
            headers={"Authorization": f"Bearer {_MISTRAL_KEY}"},
            json={"model": _EMBED_MODEL, "input": text},
            timeout=15,
        )
    except requests.exceptions.RequestException:
        return None
    if resp.status_code != 200:
        return None
    try:
        data = resp.json()
    except Exception:
        return None
    arr = data.get("data") or []
    if not arr:
        return None
    return arr[0].get("embedding")


def _cosine(a: List[float], b: List[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if not na or not nb:
        return 0.0
    return dot / (na * nb)


def upsert_document(
    db: Session,
    *,
    doc_type: str,
    doc_id: str,
    content: str,
    metadata: Optional[Dict] = None,
) -> Optional[DocumentEmbeddingDB]:
    if not rag_enabled():
        return None
    emb = _embed(content)
    if not emb:
        return None
    rec = (
        db.query(DocumentEmbeddingDB)
        .filter_by(doc_type=doc_type, doc_id=doc_id)
        .first()
    )
    if not rec:
        rec = DocumentEmbeddingDB(
            doc_type=doc_type,
            doc_id=doc_id,
            content=content,
            meta_json=metadata or {},
            embedding_json=emb,
        )
        # set embedding if vector column supports it
        try:
            rec.embedding = emb
        except Exception:
            pass
        db.add(rec)
    else:
        rec.content = content
        rec.meta_json = metadata or {}
        rec.embedding_json = emb
        try:
            rec.embedding = emb
        except Exception:
            pass
    db.commit()
    db.refresh(rec)
    return rec


def query_similar(
    db: Session,
    *,
    query_text: str,
    limit: int = 5,
    doc_type: Optional[str] = None,
    metadata_filter: Optional[Dict[str, object]] = None,
) -> List[Tuple[DocumentEmbeddingDB, float]]:
    if not rag_enabled():
        return []
    emb = _embed(query_text)
    if not emb:
        return []

    q = db.query(DocumentEmbeddingDB)
    if doc_type:
        q = q.filter_by(doc_type=doc_type)

    # Helper: apply metadata filter in Python for cross-DB compatibility.
    def _matches_meta(rec: DocumentEmbeddingDB) -> bool:
        if not metadata_filter:
            return True
        meta = getattr(rec, "meta_json", None) or getattr(rec, "metadata", None) or {}
        if not isinstance(meta, dict):
            return False
        for k, v in metadata_filter.items():
            if meta.get(k) != v:
                return False
        return True

    # If a metadata_filter is present, we intentionally do Python-side filtering.
    # This avoids DB-specific JSON query syntax and guarantees strict matching.
    if metadata_filter:
        rows = q.limit(1000).all()
        rows = [r for r in rows if _matches_meta(r)]
        scored: List[Tuple[DocumentEmbeddingDB, float]] = []
        for r in rows:
            vec = r.embedding_json if isinstance(r.embedding_json, list) else None
            if not vec:
                continue
            scored.append((r, _cosine(emb, vec)))
        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[:limit]

    # Fast path: try vector ordering if available (no metadata filter).
    try:
        rows = q.order_by(DocumentEmbeddingDB.embedding.l2_distance(emb)).limit(limit).all()
        return [(r, 0.0) for r in rows]
    except Exception:
        rows = q.limit(500).all()
        scored: List[Tuple[DocumentEmbeddingDB, float]] = []
        for r in rows:
            vec = r.embedding_json if isinstance(r.embedding_json, list) else None
            if not vec:
                continue
            scored.append((r, _cosine(emb, vec)))
        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[:limit]


def build_context(
    db: Session,
    *,
    query_text: str,
    limit: int = 5,
    doc_type: Optional[str] = None,
    metadata_filter: Optional[Dict[str, object]] = None,
) -> str:
    items = query_similar(
        db,
        query_text=query_text,
        limit=limit,
        doc_type=doc_type,
        metadata_filter=metadata_filter,
    )
    if not items:
        return ""
    parts = []
    for rec, score in items:
        snippet = (rec.content or "")[:600]
        parts.append(f"- {snippet}")
    return "\n".join(parts)


def build_context_multi(
    db: Session,
    *,
    query_text: str,
    limit: int = 5,
    doc_types: Iterable[str],
    metadata_filter: Optional[Dict[str, object]] = None,
) -> str:
    parts: List[str] = []
    for dt in doc_types:
        ctx = build_context(
            db,
            query_text=query_text,
            limit=limit,
            doc_type=dt,
            metadata_filter=metadata_filter,
        )
        if ctx:
            parts.append(ctx)
    return "\n".join([p for p in parts if p])


def add_event_documents(
    db: Session,
    *,
    doc_type: str,
    doc_id: str,
    content: str,
    metadata: Optional[Dict] = None,
    ) -> None:
    try:
        upsert_document(
            db,
            doc_type=doc_type,
            doc_id=doc_id,
            content=content,
            metadata=metadata or {},
        )
    except Exception:
        pass


def health(db: Optional[Session] = None) -> Dict[str, object]:
    """
    Lightweight RAG health for runtime checks.
    Does not call external embedding API.
    """
    out: Dict[str, object] = {
        "ok": bool(rag_enabled()),
        "enabled_env": bool(_RAG_ENABLED),
        "api_key_present": bool(_MISTRAL_KEY),
        "active": bool(rag_enabled()),
        "embed_model": _EMBED_MODEL,
    }
    if db is not None:
        try:
            count = int(db.query(DocumentEmbeddingDB).count())
            out["document_count"] = count
            out["db_ok"] = True
        except Exception as exc:
            out["db_ok"] = False
            out["db_error"] = str(exc)
    return out


def smoke_test(db: Session) -> Dict[str, object]:
    """
    End-to-end RAG smoke check:
    - verifies active config
    - executes one embedding request
    - executes one retrieval query
    """
    base = health(db)
    if not rag_enabled():
        return {
            **base,
            "ok": False,
            "detail": "rag_disabled_or_missing_api_key",
            "embed_ok": False,
            "retrieval_ok": False,
        }

    emb = _embed("smart warranty hub rag smoke check")
    if not emb:
        return {
            **base,
            "ok": False,
            "detail": "embedding_provider_unreachable",
            "embed_ok": False,
            "retrieval_ok": False,
        }

    retrieval_ok = True
    retrieval_error = None
    top_hits = 0
    try:
        hits = query_similar(db, query_text="warranty failure risk guidance", limit=1)
        top_hits = len(hits)
    except Exception as exc:
        retrieval_ok = False
        retrieval_error = str(exc)

    return {
        **base,
        "ok": bool(retrieval_ok),
        "detail": "ok" if retrieval_ok else "retrieval_failed",
        "embed_ok": True,
        "retrieval_ok": bool(retrieval_ok),
        "top_hits": int(top_hits),
        "retrieval_error": retrieval_error,
    }
