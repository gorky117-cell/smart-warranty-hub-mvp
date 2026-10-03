"""Read issue/care signals out of retrieved RAG text (fix run B3).

Replaces a bare keyword scan that treated "no failures reported" exactly like "multiple failures
reported". Each sentence is classified as an issue report, a no-issue statement or a care report;
negations ("no", "zero", "without", "not", "never", "free of") and counts ("3 failures", "multiple",
"several", "repeated") are read.
"""
from __future__ import annotations

import re
from typing import Dict, List

_ISSUE = r"(failures?|failed|faults?|errors?|issues?|defects?|recalls?|breakdowns?|malfunctions?|problems?)"
_CARE = r"(maintenance|maintained|cleaned|cleaning|serviced|servicing|descaled|filter\s+replaced)"
_NEGATION = r"(no|zero|none|nil|without|not|never|free\s+of|0)"
_WORD_COUNTS = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "multiple": 2, "several": 3, "many": 3,
                "repeated": 2, "frequent": 3, "recurring": 2}

_NEGATED_ISSUE_RE = re.compile(rf"\b{_NEGATION}\b(?:\s+\w+){{0,3}}?\s+{_ISSUE}\b", re.IGNORECASE)
_ISSUE_RE = re.compile(rf"\b{_ISSUE}\b", re.IGNORECASE)
_COUNT_RE = re.compile(rf"\b(\d+|{'|'.join(_WORD_COUNTS)})\b(?:\s+\w+){{0,3}}?\s+{_ISSUE}\b", re.IGNORECASE)
_NEGATED_CARE_RE = re.compile(rf"\b{_NEGATION}\b(?:\s+\w+){{0,3}}?\s+{_CARE}\b", re.IGNORECASE)
_CARE_RE = re.compile(rf"\b{_CARE}\b", re.IGNORECASE)


def _sentences(text: str) -> List[str]:
    return [s.strip() for s in re.split(r"(?<=[.!?;])\s+|\n+", text or "") if s.strip()]


def parse_rag_signals(text: str) -> Dict[str, object]:
    """Return {"issue_reports", "no_issue_statements", "care_reports", "evidence"}."""
    issues = 0
    no_issue = 0
    care = 0
    evidence: List[str] = []
    for sentence in _sentences(text):
        if _ISSUE_RE.search(sentence):
            if _NEGATED_ISSUE_RE.search(sentence):
                no_issue += 1
            else:
                count = 1
                for match in _COUNT_RE.finditer(sentence):
                    raw = match.group(1).lower()
                    value = int(raw) if raw.isdigit() else _WORD_COUNTS.get(raw, 1)
                    count = max(count, value)
                if count > 0:
                    issues += count
                    evidence.append(sentence[:160])
        if _CARE_RE.search(sentence) and not _NEGATED_CARE_RE.search(sentence):
            care += 1
    return {"issue_reports": issues, "no_issue_statements": no_issue, "care_reports": care, "evidence": evidence[:3]}
