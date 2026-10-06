"""Partner feed: warranty facts supplied directly by a brand or a licensed data partner (placeholder).

First in the terms source order: partner feed -> verified knowledge base -> brand website (only where
robots.txt allows; facts in SWH's words + link + checked date) -> "Estimated, please check" + link to the
brand's page. No partner is connected yet, so `lookup` always returns None. A real feed must return a
TermsResult whose facts carry the partner as source and the date the partner last updated them.
"""
from __future__ import annotations

from typing import Optional


def lookup(*, company: Optional[str], model_code: Optional[str], product_line: Optional[str], region: Optional[str]):
    return None
