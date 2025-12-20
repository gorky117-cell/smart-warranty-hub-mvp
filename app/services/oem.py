import re
from typing import Dict, Optional

import requests
from sqlalchemy import select

from ..models import Artifact, ArtifactType
from ..storage import generate_id, store
from ..db import SessionLocal
from ..db_models import OEMFetchDB
from .audit import log_action
from .oem_parsers import parse_oem_text, parse_oem_html

HEADERS = {
    "User-Agent": "SmartWarrantyHub/1.0 (+https://example.com)",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}


def fetch_oem_page(url: str, brand: str, model: str, region: Optional[str] = None) -> Artifact:
    resp = requests.get(url, headers=HEADERS, timeout=20)
    resp.raise_for_status()
    text = resp.text
    text_clean = re.sub(r"\s+", " ", text)
    parsed = parse_oem_text(text_clean, brand)
    parsed_html = parse_oem_html(text, brand)
    payload = f"Brand: {brand}\nModel: {model}\nRegion: {region or ''}\nParsed: {parsed}\nParsedHTML: {parsed_html}\n\n{text_clean}"
    artifact = Artifact(
        id=generate_id("art"),
        type=ArtifactType.portal,
        content=payload,
        source="oem-fetch",
    )
    store.add_artifact(artifact)
    # mark queue item as fetched if exists
    with SessionLocal() as db:
        stmt = select(OEMFetchDB).where(
            OEMFetchDB.url == url, OEMFetchDB.model == model, OEMFetchDB.brand == brand
        )
        row = db.execute(stmt).scalar_one_or_none()
        if row:
            row.status = "fetched"
            row.last_error = None
            db.commit()
    log_action("oem_fetch", f"Fetched {url} for {brand} {model}")
    return artifact
