from __future__ import annotations

import os
import json
from datetime import datetime
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional
from uuid import uuid4

from sqlalchemy.orm import Session

from ..db_models import ParsedFieldDB
from ..models import CanonicalWarranty
from ..storage import store
from . import diagnostics_capability
from . import predictive
from . import summary_engine
from .warranty_status import compute_warranty_status


ALLOWED_TOOLS = (
    "get_warranty_record",
    "get_invoice_evidence",
    "retrieve_terms_source",
    "get_risk_care_context",
    "create_draft_claim_checklist",
)

NOT_ALLOWED = (
    "send_oem_emails",
    "change_warranty_status",
    "submit_claims",
    "browse_arbitrary_websites",
    "execute_remote_diagnostic_commands",
    "access_another_customers_data",
)

TRACE_PATH = Path(os.getenv("AGENTIC_TRACE_FILE", "data/agentic_traces.jsonl"))


def enabled() -> bool:
    return os.getenv("AGENTIC_WORKFLOW_ENABLED", "0").strip().lower() in ("1", "true", "yes")


def _append_trace(record: Dict[str, object]) -> str:
    trace_id = f"agt_{uuid4().hex[:12]}"
    payload = {
        "id": trace_id,
        "created_at": datetime.utcnow().isoformat(),
        **record,
    }
    try:
        TRACE_PATH.parent.mkdir(parents=True, exist_ok=True)
        with TRACE_PATH.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(payload, default=str) + "\n")
    except Exception:
        pass
    return trace_id


def _record_run(
    *,
    user_id: str,
    warranty_id: str,
    status: str,
    question: Optional[str],
    tool_calls: Optional[List[Dict[str, object]]] = None,
) -> str:
    return _append_trace(
        {
            "agent": "warranty_resolution_agent",
            "user_id": user_id,
            "warranty_id": warranty_id,
            "status": status,
            "question_present": bool(question),
            "allowed_tools": list(ALLOWED_TOOLS),
            "not_allowed": list(NOT_ALLOWED),
            "tool_calls": tool_calls or [],
        }
    )


def list_traces(
    *,
    user_id: Optional[str] = None,
    warranty_id: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 100,
) -> List[Dict[str, object]]:
    if not TRACE_PATH.exists():
        return []
    rows: List[Dict[str, object]] = []
    try:
        lines = TRACE_PATH.read_text(encoding="utf-8").splitlines()
    except Exception:
        return []
    for line in reversed(lines):
        if not line.strip():
            continue
        try:
            rec = json.loads(line)
        except Exception:
            continue
        if user_id and rec.get("user_id") != user_id:
            continue
        if warranty_id and rec.get("warranty_id") != warranty_id:
            continue
        if status and rec.get("status") != status:
            continue
        rows.append(rec)
        if len(rows) >= max(1, min(int(limit or 100), 500)):
            break
    return rows


@dataclass
class AgentTrace:
    tool_calls: List[Dict[str, object]] = field(default_factory=list)

    def record(self, name: str, status: str = "ok", **details: object) -> None:
        if name not in ALLOWED_TOOLS:
            raise ValueError(f"tool_not_allowed:{name}")
        self.tool_calls.append({"tool": name, "status": status, **details})


def _safe_list(items: Optional[List[str]], fallback: str, limit: int = 6) -> List[str]:
    clean = [str(item).strip() for item in (items or []) if str(item).strip()]
    return clean[:limit] if clean else [fallback]


def _parsed_invoice_evidence(db: Session, warranty_id: str) -> Dict[str, object]:
    row = (
        db.query(ParsedFieldDB)
        .filter_by(warranty_id=warranty_id)
        .order_by(ParsedFieldDB.created_at.desc())
        .first()
    )
    if not row:
        return {"available": False, "fields": {}, "confidence": {}}
    fields = {
        "brand": row.brand,
        "model_code": row.model_code,
        "product_name": row.product_name,
        "product_category": row.product_category,
        "serial_no_present": bool(row.serial_no),
        "invoice_no_present": bool(row.invoice_no),
        "purchase_date": row.purchase_date.isoformat() if row.purchase_date else None,
    }
    return {"available": True, "fields": fields, "confidence": row.confidence or {}}


def _claim_checklist(warranty: CanonicalWarranty, evidence_status: Dict[str, object], risk: Dict[str, object]) -> List[str]:
    checklist = [
        "Keep invoice or purchase receipt ready.",
        "Keep product model and serial number ready.",
    ]
    if evidence_status.get("requires_oem_verification"):
        checklist.append("Verify official OEM warranty terms before treating coverage as confirmed.")
    checklist.extend(_safe_list(warranty.claim_steps, "Use the OEM support flow or authorised service channel.", limit=4))
    if (risk.get("risk_label") or "").upper() in {"MEDIUM", "HIGH"}:
        checklist.append("Include recent symptoms, usage notes, photos or logs when contacting support.")
    checklist.append("Do not submit a claim automatically; review this checklist first.")
    return list(dict.fromkeys(checklist))


def resolve_warranty(
    db: Session,
    *,
    user_id: str,
    warranty_id: str,
    question: Optional[str] = None,
) -> Dict[str, object]:
    if not enabled():
        trace_id = _record_run(
            user_id=user_id,
            warranty_id=warranty_id,
            status="disabled",
            question=question,
            tool_calls=[],
        )
        return {
            "ok": True,
            "status": "disabled",
            "trace_id": trace_id,
            "message": "Controlled warranty agent is disabled. Set AGENTIC_WORKFLOW_ENABLED=1 to enable.",
            "allowed_tools": list(ALLOWED_TOOLS),
            "not_allowed": list(NOT_ALLOWED),
        }

    trace = AgentTrace()
    warranty = store.get_warranty_db(warranty_id)
    if not warranty:
        trace.record("get_warranty_record", status="not_found", warranty_id=warranty_id)
        trace_id = _record_run(
            user_id=user_id,
            warranty_id=warranty_id,
            status="not_found",
            question=question,
            tool_calls=trace.tool_calls,
        )
        return {
            "ok": False,
            "status": "not_found",
            "trace_id": trace_id,
            "message": "Warranty record not found.",
            "tool_calls": trace.tool_calls,
        }
    trace.record("get_warranty_record", warranty_id=warranty_id)

    invoice_evidence = _parsed_invoice_evidence(db, warranty_id)
    trace.record(
        "get_invoice_evidence",
        status="ok" if invoice_evidence.get("available") else "missing",
        fields=list((invoice_evidence.get("fields") or {}).keys()),
    )

    evidence_status = summary_engine.build_evidence_summary(warranty)
    trace.record(
        "retrieve_terms_source",
        source_type=evidence_status.get("source_type"),
        requires_oem_verification=evidence_status.get("requires_oem_verification"),
    )

    risk = predictive.score_warranty(user_id, warranty_id)
    capability = diagnostics_capability.infer_capability(
        product_name=warranty.product_name,
        brand=warranty.brand,
        model_code=warranty.model_code,
        alternatives=warranty.alternatives,
    )
    trace.record("get_risk_care_context", risk_label=risk.get("risk_label"), diagnostic_mode=capability.get("mode"))

    warranty_status = compute_warranty_status(
        purchase_date=warranty.purchase_date,
        expiry_date=warranty.expiry_date,
        coverage_months=warranty.coverage_months,
    )
    layman = summary_engine.build_layman_summary(warranty)
    checklist = _claim_checklist(warranty, evidence_status, risk)
    trace.record("create_draft_claim_checklist", item_count=len(checklist))

    missing = []
    if not warranty.serial_no:
        missing.append("serial number")
    if not getattr(warranty, "region_code", None):
        missing.append("country/region")
    if evidence_status.get("requires_oem_verification"):
        missing.append("confirmed official warranty terms")

    trace_id = _record_run(
        user_id=user_id,
        warranty_id=warranty_id,
        status="draft",
        question=question,
        tool_calls=trace.tool_calls,
    )

    return {
        "ok": True,
        "status": "draft",
        "trace_id": trace_id,
        "agent": "warranty_resolution_agent",
        "question": question,
        "allowed_tools": list(ALLOWED_TOOLS),
        "not_allowed": list(NOT_ALLOWED),
        "tool_calls": trace.tool_calls,
        "warranty_id": warranty_id,
        "product": {
            "brand": warranty.brand,
            "model_code": warranty.model_code,
            "product_name": warranty.product_name,
            "serial_no_present": bool(warranty.serial_no),
        },
        "invoice_evidence": invoice_evidence,
        "evidence_status": evidence_status,
        "warranty_status": warranty_status,
        "risk_care_context": {
            "risk_label": risk.get("risk_label"),
            "risk_score": risk.get("risk_score"),
            "reasons": risk.get("reasons") or [],
            "disclaimer": risk.get("disclaimer"),
            "diagnostic_mode": capability.get("mode"),
            "diagnostic_recommended_action": capability.get("recommended_action"),
        },
        "answer": layman.get("overview"),
        "missing_or_uncertain": missing,
        "draft_claim_checklist": checklist,
        "safety_note": "Draft explanation only. The agent cannot change warranty status, submit claims, contact OEMs, browse arbitrary sites, run remote commands, or access another customer's data.",
    }
