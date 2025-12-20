from __future__ import annotations

import json
import os
import uuid
import datetime as dt
import logging
from typing import List, Dict, Optional, Tuple

logger = logging.getLogger(__name__)

QUESTIONS_PATH = os.path.join("data", "oem_questions.jsonl")
ANSWERS_PATH = os.path.join("data", "oem_question_answers.jsonl")


def _ensure_dir(path: str):
    os.makedirs(os.path.dirname(path), exist_ok=True)


def _append_jsonl(path: str, rec: Dict):
    _ensure_dir(path)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec) + "\n")


def _load_jsonl(path: str) -> List[Dict]:
    if not os.path.exists(path):
        return []
    out: List[Dict] = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            try:
                out.append(json.loads(line))
            except Exception:
                continue
    return out


def publish_question(target: Dict, question: Dict) -> Dict:
    now = dt.datetime.utcnow().isoformat()
    rec = {
        "id": question.get("id") or f"oemq_{uuid.uuid4().hex[:10]}",
        "brand": target.get("brand"),
        "model_code": target.get("model_code"),
        "product_type": target.get("product_type"),
        "region": target.get("region"),
        "text": question.get("text", "").strip(),
        "answer_type": question.get("answer_type") or "text",
        "options": question.get("options") or [],
        "priority": question.get("priority", 50),
        "enabled": bool(question.get("enabled", True)),
        "source": question.get("source", "manual"),
        "created_at": now,
    }
    _append_jsonl(QUESTIONS_PATH, rec)
    return rec


def list_active(filters: Dict) -> List[Dict]:
    all_q = _load_jsonl(QUESTIONS_PATH)
    out = []
    for q in all_q:
        if not q.get("enabled", True):
            continue
        if filters.get("brand") and q.get("brand") != filters.get("brand"):
            continue
        if filters.get("model_code") and q.get("model_code") != filters.get("model_code"):
            continue
        if filters.get("region") and q.get("region") != filters.get("region"):
            continue
        if filters.get("product_type") and q.get("product_type") != filters.get("product_type"):
            continue
        out.append(q)
    out.sort(key=lambda x: x.get("priority", 50))
    return out


def disable_question(question_id: str) -> bool:
    all_q = _load_jsonl(QUESTIONS_PATH)
    changed = False
    for q in all_q:
        if q.get("id") == question_id:
            q["enabled"] = False
            changed = True
    if changed:
        _ensure_dir(QUESTIONS_PATH)
        with open(QUESTIONS_PATH, "w", encoding="utf-8") as f:
            for q in all_q:
                f.write(json.dumps(q) + "\n")
    return changed


def _answered_ids(user_id: str, warranty_id: str) -> set:
    answered = set()
    for rec in _load_jsonl(ANSWERS_PATH):
        if rec.get("user_id") == user_id and rec.get("warranty_id") == warranty_id:
            answered.add(rec.get("question_id"))
    return answered


def get_next_oem_question(user_id: str, warranty_id: str, context: Dict) -> Optional[Dict]:
    answered = _answered_ids(user_id, warranty_id)
    active = list_active(context)
    for q in active:
        if q.get("id") not in answered:
            return q
    return None


def record_oem_answer(user_id: str, warranty_id: str, question_id: str, answer: str, meta: Optional[Dict] = None) -> None:
    rec = {
        "user_id": user_id,
        "warranty_id": warranty_id,
        "question_id": question_id,
        "answer": answer,
        "meta": meta or {},
        "ts": dt.datetime.utcnow().isoformat(),
    }
    _append_jsonl(ANSWERS_PATH, rec)
