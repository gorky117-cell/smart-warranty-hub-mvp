from __future__ import annotations

import os
import json
import logging
from typing import List, Dict
import requests

logger = logging.getLogger(__name__)

FALLBACK_QUESTIONS = [
    {"text": "Where is the product used most?", "answer_type": "choice", "options": ["Home", "Office", "Outdoor", "Mixed"]},
    {"text": "Average daily usage?", "answer_type": "choice", "options": ["Low", "Medium", "High"]},
    {"text": "Do you notice voltage fluctuations?", "answer_type": "choice", "options": ["Yes", "No", "Not sure"]},
]


def status():
    enabled = os.environ.get("ENABLE_LLM_QUESTIONS", "0") == "1"
    base = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
    model = os.environ.get("OLLAMA_MODEL", "llama3.1")
    reachable = False
    error = None
    if enabled:
        try:
            r = requests.get(f"{base}/api/tags", timeout=2)
            reachable = r.status_code == 200
        except Exception as e:
            error = str(e)
    return {"enabled": enabled, "base_url": base, "model": model, "reachable": reachable, "error": error}


def generate_questions(context: Dict, n: int = 5) -> List[Dict]:
    if os.environ.get("ENABLE_LLM_QUESTIONS", "0") != "1":
        return FALLBACK_QUESTIONS[:n]
    base = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
    model = os.environ.get("OLLAMA_MODEL", "llama3.1")
    prompt = (
        "Return JSON only: {\"questions\":[{\"text\":\"...\",\"answer_type\":\"choice|boolean|text\",\"options\":[...]},...]}. "
        "Keep it concise and customer-friendly."
    )
    try:
        resp = requests.post(
            f"{base}/api/generate",
            json={"model": model, "prompt": prompt, "stream": False},
            timeout=4,
        )
        if resp.status_code != 200:
            return FALLBACK_QUESTIONS[:n]
        data = resp.json()
        txt = data.get("response", "")
        parsed = json.loads(txt)
        arr = parsed.get("questions") if isinstance(parsed, dict) else parsed
        out = []
        for q in arr or []:
            at = q.get("answer_type")
            if at not in ("choice", "boolean", "text"):
                at = "text"
            opts = q.get("options") if isinstance(q.get("options"), list) else []
            out.append({"text": q.get("text", ""), "answer_type": at, "options": opts})
            if len(out) >= n:
                break
        return out or FALLBACK_QUESTIONS[:n]
    except Exception as e:
        logger.warning("ollama question gen failed", exc_info=e)
        return FALLBACK_QUESTIONS[:n]
