from __future__ import annotations

import re
from typing import Optional

import requests
from bs4 import BeautifulSoup

def fetch_terms(*, brand: Optional[str], model_code: Optional[str], category: Optional[str], region: Optional[str]) -> Optional[dict]:
    # Placeholder scraper disabled (no real OEM URL configured).
    return None
