from __future__ import annotations

import math
import os
from typing import List, Dict, Optional, Tuple

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
) -> List[Tuple[DocumentEmbeddingDB, float]]:
    if not rag_enabled():
        return []
    emb = _embed(query_text)
    if not emb:
        return []

    # Try vector DB ordering if available
    q = db.query(DocumentEmbeddingDB)
    if doc_type:
        q = q.filter_by(doc_type=doc_type)
    try:
        # pgvector: lower distance = better
        rows = q.order_by(DocumentEmbeddingDB.embedding.l2_distance(emb)).limit(limit).all()
        return [(r, 0.0) for r in rows]
    except Exception:
        rows = q.limit(500).all()
        scored = []
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
) -> str:
    items = query_similar(db, query_text=query_text, limit=limit, doc_type=doc_type)
    if not items:
        return ""
    parts = []
    for rec, score in items:
        snippet = (rec.content or "")[:600]
        parts.append(f"- {snippet}")
    return "\n".join(parts)


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
