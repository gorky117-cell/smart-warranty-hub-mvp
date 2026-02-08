from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Dict, Any, List

from sqlalchemy.orm import Session

from ..db_models import OemIssueSignalDB


@dataclass
class IssueSignalSummary:
    risk_delta: float
    reasons: List[str]


def record_issue_signal(
    db: Session,
    *,
    brand: Optional[str],
    model_code: Optional[str],
    product_type: Optional[str],
    region: Optional[str],
    issue_type: Optional[str],
    severity: Optional[float],
    count: Optional[int],
    source_url: Optional[str] = None,
) -> OemIssueSignalDB:
    rec = OemIssueSignalDB(
        brand=brand,
        model_code=model_code,
        product_type=product_type,
        region=region,
        issue_type=issue_type,
        severity=severity,
        count=count,
        source_url=source_url,
    )
    db.add(rec)
    db.commit()
    db.refresh(rec)
    try:
        from .rag import add_event_documents, rag_enabled
        if rag_enabled():
            add_event_documents(
                db,
                doc_type="oem_issue",
                doc_id=f"oem_issue:{rec.id}",
                content=f"brand={brand} model={model_code} region={region} issue={issue_type} severity={severity} count={count}",
                metadata={
                    "brand": brand,
                    "model_code": model_code,
                    "product_type": product_type,
                    "region": region,
                    "issue_type": issue_type,
                },
            )
    except Exception:
        pass
    return rec


def summarize_issue_signals(
    db: Session,
    *,
    brand: Optional[str],
    model_code: Optional[str],
    product_type: Optional[str],
    region: Optional[str],
) -> IssueSignalSummary:
    q = db.query(OemIssueSignalDB)
    if brand:
        q = q.filter_by(brand=brand)
    if model_code:
        q = q.filter_by(model_code=model_code)
    if product_type:
        q = q.filter_by(product_type=product_type)
    if region:
        q = q.filter_by(region=region)
    rows = q.all()
    if not rows:
        return IssueSignalSummary(0.0, [])
    total = 0
    weighted = 0.0
    for r in rows:
        c = int(r.count or 1)
        sev = float(r.severity or 0.5)
        total += c
        weighted += sev * c
    avg_sev = weighted / total if total else 0.0
    # Map severity [0-1] to delta [0-0.2]
    delta = min(0.2, max(0.0, avg_sev * 0.2))
    reasons = [f"OEM issue signals present (avg severity {avg_sev:.2f})"]
    return IssueSignalSummary(delta, reasons)
