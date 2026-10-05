"""Customers' original documents (invoice, warranty card, photos) and where their bytes are kept.

`DOCUMENT_STORE` picks the backend for new files:
- "db" (default): the bytes are stored in the `documents` row (Postgres BYTEA / SQLite BLOB), so they are kept
  with the database and its backups and survive redeploys.
- "local" (only when set explicitly): the file stays in data/uploads on the app's disk. On a host without a
  persistent volume (Railway by default) these files are lost on every redeploy.
- "s3": via `object_store.put_bytes` (OBJECT_STORE_* settings); falls back to local when not configured.

Every read checks the owner. A document whose bytes are gone is listed as "no longer available".
"""
from __future__ import annotations

import hashlib
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from sqlalchemy.orm import Session

from ..db_models import DocumentDB
from ..storage import generate_id

KINDS: Dict[str, str] = {
    "invoice": "Invoice / bill",
    "warranty_card": "Warranty card",
    "photo": "Photo of the product",
    "manual": "User manual",
    "other": "Other document",
}
CONTENT_TYPES = {
    ".pdf": "application/pdf",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
    ".txt": "text/plain",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}
# Shown in the browser; anything else is always downloaded.
INLINE_TYPES = {"application/pdf", "image/png", "image/jpeg", "image/webp", "text/plain"}
UPLOADS_DIR = Path(__file__).resolve().parents[2] / "data" / "uploads"


def backend() -> str:
    value = (os.getenv("DOCUMENT_STORE") or "db").strip().lower()
    return value if value in ("local", "db", "s3") else "db"


def kind_for_artifact(artifact_type: Optional[str], suffix: str = "") -> str:
    value = str(getattr(artifact_type, "value", artifact_type) or "").lower()
    if value == "invoice":
        return "invoice"
    if value == "label":
        return "warranty_card"
    if value == "manual":
        return "manual"
    if suffix.lower() in (".png", ".jpg", ".jpeg", ".webp"):
        return "photo"
    return "other"


def _content_type(filename: str) -> str:
    return CONTENT_TYPES.get(Path(filename).suffix.lower(), "application/octet-stream")


def save(
    db: Session,
    *,
    owner: str,
    warranty_id: Optional[str],
    kind: str,
    filename: str,
    local_path: Optional[Path] = None,
    data: Optional[bytes] = None,
) -> DocumentDB:
    """Record a document; the same file for the same product and owner is stored once."""
    if data is None:
        data = Path(local_path).read_bytes() if local_path else b""
    digest = hashlib.sha256(data).hexdigest()
    existing = (
        db.query(DocumentDB)
        .filter_by(owner_user_id=owner, warranty_id=warranty_id, sha256=digest)
        .first()
    )
    if existing:
        return existing
    name = Path(filename or "document").name[:120] or "document"
    kind = kind if kind in KINDS else "other"
    doc = DocumentDB(
        id=generate_id("doc"),
        owner_user_id=owner,
        warranty_id=warranty_id,
        kind=kind,
        filename=name,
        content_type=_content_type(name),
        size_bytes=len(data),
        sha256=digest,
        uploaded_at=datetime.utcnow(),
    )
    mode = backend()
    if mode == "db":
        doc.storage, doc.data = "db", data
    elif mode == "s3":
        from .object_store import put_bytes

        ref = put_bytes(data, key=f"documents/{owner}/{doc.id}{Path(name).suffix.lower()}", content_type=doc.content_type)
        doc.storage = "s3" if ref.startswith("s3://") else "local"
        doc.location = ref
    else:
        if local_path is None:
            UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
            local_path = UPLOADS_DIR / f"{doc.id}{Path(name).suffix.lower()}"
            Path(local_path).write_bytes(data)
        doc.storage, doc.location = "local", str(local_path)
    db.add(doc)
    db.commit()
    db.refresh(doc)
    return doc


def read_bytes(doc: DocumentDB) -> Optional[bytes]:
    """The file's bytes, or None when they are no longer available."""
    try:
        if doc.storage == "db":
            return bytes(doc.data) if doc.data is not None else None
        if doc.storage == "s3" and doc.location and doc.location.startswith("s3://"):
            import boto3  # type: ignore

            bucket, _, key = doc.location[len("s3://"):].partition("/")
            client = boto3.client(
                "s3",
                endpoint_url=os.getenv("OBJECT_STORE_S3_ENDPOINT"),
                region_name=os.getenv("OBJECT_STORE_S3_REGION", "auto"),
                aws_access_key_id=os.getenv("OBJECT_STORE_S3_ACCESS_KEY"),
                aws_secret_access_key=os.getenv("OBJECT_STORE_S3_SECRET_KEY"),
            )
            return client.get_object(Bucket=bucket, Key=key)["Body"].read()
        if doc.location and Path(doc.location).is_file():
            return Path(doc.location).read_bytes()
    except Exception:
        return None
    return None


def available(doc: DocumentDB) -> bool:
    if doc.storage == "db":
        return doc.data is not None
    if doc.storage == "local":
        return bool(doc.location) and Path(doc.location).is_file()
    return True


def describe(doc: DocumentDB) -> dict:
    """What the customer sees (no storage paths, keys or owner)."""
    return {
        "id": doc.id,
        "warranty_id": doc.warranty_id,
        "kind": doc.kind,
        "kind_label": KINDS.get(doc.kind, KINDS["other"]),
        "filename": doc.filename,
        "content_type": doc.content_type,
        "size_bytes": doc.size_bytes,
        "uploaded_at": doc.uploaded_at.isoformat() if doc.uploaded_at else None,
        "available": available(doc),
        "viewable": doc.content_type in INLINE_TYPES,
    }


def list_for(db: Session, *, owner: str, warranty_id: str) -> List[DocumentDB]:
    return (
        db.query(DocumentDB)
        .filter_by(owner_user_id=owner, warranty_id=warranty_id)
        .order_by(DocumentDB.uploaded_at.desc())
        .all()
    )


def get_owned(db: Session, *, owner: str, doc_id: str) -> Optional[DocumentDB]:
    """The document only when `owner` owns it; otherwise None (callers answer 404, never revealing it exists)."""
    return db.query(DocumentDB).filter_by(id=doc_id, owner_user_id=owner).first()


def delete(db: Session, doc: DocumentDB) -> None:
    if doc.storage == "local" and doc.location:
        others = db.query(DocumentDB).filter(DocumentDB.location == doc.location, DocumentDB.id != doc.id).count()
        if not others:
            try:
                Path(doc.location).unlink(missing_ok=True)
            except Exception:
                pass
    db.delete(doc)
    db.commit()


def recover_old_uploads(db: Session, *, owner: str, warranty_id: str) -> List[dict]:
    """Invoices uploaded before "My documents" existed have no document row, only the upload job's file path.
    A file still on disk is saved now (so it survives the next redeploy); a file that is gone is listed as
    "no longer available" so the owner knows to upload it again. Returns those placeholder entries."""
    from ..db_models import PipelineJobDB

    if db.query(DocumentDB.id).filter_by(owner_user_id=owner, warranty_id=warranty_id, kind="invoice").first():
        return []
    missing = []
    jobs = (
        db.query(PipelineJobDB)
        .filter(PipelineJobDB.warranty_id == warranty_id, PipelineJobDB.source_path.isnot(None))
        .order_by(PipelineJobDB.created_at.desc())
        .all()
    )
    for job in jobs:
        path = Path(job.source_path)
        if path.is_file():
            save(db, owner=owner, warranty_id=warranty_id, kind="invoice", filename=f"invoice{path.suffix.lower()}",
                 data=path.read_bytes())
            return []
        missing.append({
            "id": None,
            "warranty_id": warranty_id,
            "kind": "invoice",
            "kind_label": KINDS["invoice"],
            "filename": "Invoice you uploaded earlier",
            "content_type": None,
            "size_bytes": 0,
            "uploaded_at": job.created_at.isoformat() if job.created_at else None,
            "available": False,
            "viewable": False,
            "missing_upload": True,
        })
    return missing[:1]
