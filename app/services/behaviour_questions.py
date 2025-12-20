from __future__ import annotations

import json
import os
import logging
from typing import List, Dict, Optional, Tuple

logger = logging.getLogger(__name__)

DATA_PATH = os.path.join("data", "behaviour_answers.jsonl")


QUESTION_BANK: List[Dict] = [
    {"id": "q1_usage_location", "text": "Where is the product used most?", "answer_type": "choice", "options": ["Home", "Office", "Outdoor", "Mixed"], "tags": ["environment"]},
    {"id": "q2_daily_usage", "text": "Average daily usage?", "answer_type": "choice", "options": ["Low", "Medium", "High"], "tags": ["usage"]},
    {"id": "q3_voltage", "text": "Do you notice voltage fluctuations?", "answer_type": "choice", "options": ["Yes", "No", "Not sure"], "tags": ["power"]},
    {"id": "q4_install", "text": "Installed by authorized technician?", "answer_type": "choice", "options": ["Yes", "No", "Not sure"], "tags": ["care"]},
    {"id": "q5_environment", "text": "Environment?", "answer_type": "choice", "options": ["Humid", "Dusty", "Normal"], "tags": ["environment"]},
    {"id": "q6_overheat", "text": "Ever overheated or shut down unexpectedly?", "answer_type": "choice", "options": ["Yes", "No"], "tags": ["issues"]},
]


def _ensure_data_path():
    os.makedirs(os.path.dirname(DATA_PATH), exist_ok=True)


def _load_answers(user_id: str, warranty_id: str) -> List[Dict]:
    """Load all answers for a user+warranty from JSONL (fallback when Mongo not used)."""
    if not os.path.exists(DATA_PATH):
        return []
    results: List[Dict] = []
    try:
        with open(DATA_PATH, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    rec = json.loads(line)
                except Exception:
                    continue
                if rec.get("user_id") == user_id and rec.get("warranty_id") == warranty_id:
                    results.append(rec)
    except Exception as e:
        logger.exception("Failed to read behaviour answers file", exc_info=e)
    return results


def _append_answer(rec: Dict):
    _ensure_data_path()
    try:
        with open(DATA_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec) + "\n")
    except Exception as e:
        logger.exception("Failed to append behaviour answer", exc_info=e)


def get_next_question(user_id: str, warranty_id: str) -> Tuple[Optional[Dict], bool]:
    """
    Return next unanswered question and done flag.
    """
    answered = {a.get("question_id") for a in _load_answers(user_id, warranty_id)}
    for q in QUESTION_BANK:
        if q["id"] not in answered:
            return q, False
    return None, True


def record_answer(user_id: str, warranty_id: str, question_id: str, answer: str) -> bool:
    rec = {
        "user_id": user_id,
        "warranty_id": warranty_id,
        "question_id": question_id,
        "answer": answer,
    }
    _append_answer(rec)
    return True
