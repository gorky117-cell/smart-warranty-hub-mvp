from __future__ import annotations

import re
from typing import Tuple


POSITIVE_WORDS = {
    "good", "great", "excellent", "amazing", "love", "loved", "like", "liked", "satisfied",
    "happy", "perfect", "awesome", "reliable", "durable", "value", "worth", "recommend",
}
NEGATIVE_WORDS = {
    "bad", "poor", "terrible", "awful", "hate", "hated", "broken", "issue", "problem",
    "defect", "fault", "return", "refund", "waste", "disappointed", "worst", "unreliable",
}


def analyze_sentiment(text: str) -> Tuple[float, int, int]:
    """
    Very lightweight sentiment score.
    Returns (score_0_1, pos_count, neg_count).
    """
    if not text:
        return 0.5, 0, 0
    tokens = re.findall(r"[a-zA-Z']+", text.lower())
    pos = sum(1 for t in tokens if t in POSITIVE_WORDS)
    neg = sum(1 for t in tokens if t in NEGATIVE_WORDS)
    total = pos + neg
    if total == 0:
        return 0.5, 0, 0
    raw = (pos - neg) / max(total, 1)
    # map [-1,1] -> [0,1]
    score = max(0.0, min(1.0, (raw + 1.0) / 2.0))
    return score, pos, neg
