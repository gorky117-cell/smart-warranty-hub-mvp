import re
from typing import Dict, Optional

from sqlalchemy import select

from ..models import Artifact, ArtifactType
from ..storage import generate_id, store
from ..db import SessionLocal
from ..db_models import OEMFetchDB
from .audit import log_action
from .oem_parsers import parse_oem_text, parse_oem_html
from . import oem_adapters, oem_source_policy


def fetch_oem_page(url: str, brand: str, model: str, region: Optional[str] = None) -> Artifact:
    adapter = oem_adapters.get_adapter(brand)
    if adapter:
        fetched = adapter.fetch(url=url, model=model, region=region)
        if not fetched.get("ok"):
            raise ValueError(str(fetched.get("reason") or "oem_adapter_blocked"))
        text_clean = str(fetched.get("text") or "")
        parsed = fetched.get("parsed_text") or {}
        parsed_html = fetched.get("parsed_html") or {}
        source_type = fetched.get("source_type") or "approved_oem_adapter"
    else:
        if not oem_source_policy.manual_url_allowed(url, brand):
            raise ValueError("url_not_approved_for_oem_fetch")
        import requests

        resp = requests.get(url, headers=oem_adapters.HEADERS, timeout=20)
        resp.raise_for_status()
        text = resp.text
        text_clean = re.sub(r"\s+", " ", text)
        parsed = parse_oem_text(text_clean, brand)
        parsed_html = parse_oem_html(text, brand)
        source_type = "approved_oem_fetch"
    payload = (
        f"Brand: {brand}\nModel: {model}\nRegion: {region or ''}\n"
        f"SourceType: {source_type}\nParsed: {parsed}\nParsedHTML: {parsed_html}\n\n{text_clean}"
    )
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
