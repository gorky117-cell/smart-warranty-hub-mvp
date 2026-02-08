from __future__ import annotations

import os
import re
import time
import hashlib
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from urllib.parse import urlparse
from urllib import robotparser

import requests
from bs4 import BeautifulSoup
from sqlalchemy.orm import Session

from ..db_models import WarrantyDB, ProductReviewDB, ReviewPageDB
from .review_sources import load_review_sources
from .sentiment import analyze_sentiment
from .object_store import put_bytes
from .web_search import search_web
from .peer_review import record_peer_signal
from .audit import log_action


USER_AGENT = os.getenv("REVIEW_CRAWLER_UA", "SmartWarrantyHubBot/1.0")


@dataclass
class ProductSeed:
    brand: str
    model_code: Optional[str]
    product_name: str
    region: str

    @property
    def key(self) -> str:
        model = self.model_code or ""
        name = self.product_name or ""
        return f"{self.brand}|{model or name}|{self.region}"


def _robots_allowed(url: str, cache: Dict[str, robotparser.RobotFileParser]) -> bool:
    if os.getenv("REVIEW_ROBOTS_RESPECT", "true").lower() != "true":
        return True
    parsed = urlparse(url)
    base = f"{parsed.scheme}://{parsed.netloc}"
    if base in cache:
        rp = cache[base]
    else:
        rp = robotparser.RobotFileParser()
        try:
            rp.set_url(f"{base}/robots.txt")
            rp.read()
        except Exception:
            # If robots can't be read, default to allow to avoid blocking whole crawl.
            return True
        cache[base] = rp
    return rp.can_fetch(USER_AGENT, url)


def _allowed_domain(url: str, domains: List[str]) -> bool:
    host = urlparse(url).netloc.lower()
    deny = os.getenv("REVIEW_DENYLIST_DOMAINS", "")
    deny_list = [d.strip().lower() for d in deny.split(",") if d.strip()]
    if any(host.endswith(d) for d in deny_list):
        return False
    return any(host.endswith(d) for d in domains)


def _normalize_whitespace(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _extract_reviews(html: str) -> Tuple[List[str], Optional[float]]:
    soup = BeautifulSoup(html, "html.parser")
    # Remove scripts/styles
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    text = _normalize_whitespace(soup.get_text(" "))
    if not text:
        return [], None
    # Try to collect review blocks
    candidates = []
    for el in soup.find_all(True):
        cls = " ".join(el.get("class", [])).lower()
        if "review" in cls or "comment" in cls or "rating" in cls:
            snippet = _normalize_whitespace(el.get_text(" "))
            if len(snippet) > 40:
                candidates.append(snippet)
    # Fallback to chunks of main text
    if not candidates:
        chunks = [c.strip() for c in re.split(r"[.!?]\s+", text) if len(c.strip()) > 60]
        candidates = chunks[:10]

    # Rating extraction (very heuristic)
    rating = None
    m = re.search(r"([0-5](?:\.\d)?)\s*(?:/|out of)\s*5", text, re.IGNORECASE)
    if m:
        try:
            rating = float(m.group(1))
        except Exception:
            rating = None
    return candidates, rating


def _fetch(url: str, timeout: int = 12) -> Tuple[Optional[str], Optional[str], Optional[int]]:
    last_err = None
    retries = int(os.getenv("REVIEW_FETCH_RETRIES", "2"))
    for _ in range(max(1, retries)):
        try:
            resp = requests.get(
                url,
                headers={"User-Agent": USER_AGENT, "Accept-Language": "en-IN,en;q=0.9"},
                timeout=timeout,
            )
            if resp.status_code >= 500:
                last_err = f"http_{resp.status_code}"
                continue
            if resp.status_code >= 400:
                return None, f"http_{resp.status_code}", resp.status_code
            return resp.text, None, resp.status_code
        except requests.exceptions.RequestException as exc:
            last_err = str(exc)
            continue
    return None, last_err or "request_failed", None


def _hash_url(url: str) -> str:
    return hashlib.sha256(url.encode("utf-8")).hexdigest()


def _build_queries(seed: ProductSeed, domains: List[str]) -> List[str]:
    base = f"{seed.brand} {seed.model_code or ''} {seed.product_name}".strip()
    queries = []
    for d in domains:
        queries.append(f"{base} review site:{d}")
    return queries


def get_product_seeds(db: Session, region: Optional[str]) -> List[ProductSeed]:
    rows = db.query(WarrantyDB).all()
    seeds: Dict[str, ProductSeed] = {}
    for r in rows:
        brand = (r.brand or "").strip()
        model = (r.model_code or "").strip()
        name = (r.product_name or "").strip()
        reg = (r.region_code or region or "IN").strip()
        if not brand or (not model and not name):
            continue
        key = f"{brand}|{model or name}|{reg}"
        seeds[key] = ProductSeed(brand=brand, model_code=model or None, product_name=name, region=reg)
    if seeds:
        return list(seeds.values())

    # fallback to seed file if no warranties exist yet
    try:
        import json
        from pathlib import Path
        path = Path(__file__).resolve().parents[2] / "data" / "review_seed_products.json"
        if path.exists():
            data = json.loads(path.read_text(encoding="utf-8"))
            for item in data:
                brand = (item.get("brand") or "").strip()
                model = (item.get("model_code") or "").strip()
                name = (item.get("product_name") or "").strip()
                reg = (item.get("region") or region or "IN").strip()
                if not brand or (not model and not name):
                    continue
                key = f"{brand}|{model or name}|{reg}"
                seeds[key] = ProductSeed(brand=brand, model_code=model or None, product_name=name, region=reg)
    except Exception:
        pass
    return list(seeds.values())


def crawl_reviews(db: Session, *, region: str = "IN") -> Dict[str, int]:
    sources = load_review_sources()
    if not sources:
        return {"pages": 0, "reviews": 0}

    max_queries = int(os.getenv("REVIEW_MAX_QUERIES_PER_PRODUCT", "5"))
    max_results = int(os.getenv("REVIEW_MAX_RESULTS_PER_QUERY", "5"))
    max_pages = int(os.getenv("REVIEW_MAX_PAGES", "30"))
    max_pages_per_domain = int(os.getenv("REVIEW_MAX_PAGES_PER_DOMAIN", "10"))
    ttl_hours = int(os.getenv("REVIEW_CRAWL_TTL_HOURS", "24"))

    seeds = get_product_seeds(db, region)
    if not seeds:
        return {"pages": 0, "reviews": 0}

    robots_cache: Dict[str, robotparser.RobotFileParser] = {}
    domain_counts: Dict[str, int] = {}
    pages_crawled = 0
    reviews_added = 0
    now = datetime.utcnow()

    for seed in seeds:
        if pages_crawled >= max_pages:
            break
        for source in sources:
            if pages_crawled >= max_pages:
                break
            if source.get("region") not in (None, "", "*", seed.region, region):
                continue
            domains = source.get("domains") or []
            if not domains:
                continue
            queries = _build_queries(seed, domains)[:max_queries]
            for q in queries:
                if pages_crawled >= max_pages:
                    break
                results = search_web(
                    q,
                    count=max_results,
                    provider=os.getenv("REVIEW_SEARCH_PROVIDER", None),
                    timeout=int(os.getenv("REVIEW_SEARCH_TIMEOUT_SEC", "8")),
                )
                for res in results:
                    url = res.get("url") or ""
                    if not url:
                        continue
                    if not _allowed_domain(url, domains):
                        continue
                    host = urlparse(url).netloc.lower()
                    if domain_counts.get(host, 0) >= max_pages_per_domain:
                        continue
                    if not _robots_allowed(url, robots_cache):
                        continue
                    # TTL check
                    existing = db.query(ReviewPageDB).filter_by(url=url).first()
                    if existing and existing.fetched_at and existing.fetched_at >= (now - timedelta(hours=ttl_hours)):
                        continue
                    html, err, status = _fetch(url)
                    domain_counts[host] = domain_counts.get(host, 0) + 1
                    page = existing or ReviewPageDB(url=url)
                    page.source = source.get("name")
                    page.product_key = seed.key
                    page.http_status = status
                    page.last_error = err
                    if html:
                        page.content_type = "text/html"
                        page.text_excerpt = _normalize_whitespace(html)[:800]
                        snapshot_uri = put_bytes(
                            html.encode("utf-8"),
                            key=f"reviews/{_hash_url(url)}.html",
                            content_type="text/html",
                        )
                        page.snapshot_uri = snapshot_uri
                        page.fetched_at = datetime.utcnow()
                        reviews, rating = _extract_reviews(html)
                        for text in reviews:
                            sentiment, _, _ = analyze_sentiment(text)
                            rec = ProductReviewDB(
                                brand=seed.brand,
                                model_code=seed.model_code,
                                product_type=None,
                                region=seed.region,
                                source=source.get("name"),
                                url=url,
                                rating=rating,
                                sentiment=sentiment,
                                text=text[:4000],
                            )
                            db.add(rec)
                            reviews_added += 1
                        pages_crawled += 1
                        log_action("review_page_fetched", f"url={url} reviews={len(reviews)}")
                    if not existing:
                        db.add(page)
                    db.commit()
                    time.sleep(float(os.getenv("REVIEW_CRAWL_DELAY_SEC", "0.5")))

        # After source loop, update peer signals for the product
        try:
            rows = (
                db.query(ProductReviewDB)
                .filter_by(brand=seed.brand, model_code=seed.model_code, region=seed.region)
                .all()
            )
            if rows:
                avg_rating = sum(r.rating or 0.0 for r in rows) / len(rows)
                avg_sent = sum(r.sentiment or 0.0 for r in rows) / len(rows)
                failure_keywords = _extract_failure_keywords(rows)
                record_peer_signal(
                    db=db,
                    product_type=None,
                    brand=seed.brand,
                    model=seed.model_code,
                    symptom_keyword=None,
                    severity_hint=None,
                    source="review_crawler",
                    avg_rating=avg_rating,
                    review_sentiment=avg_sent,
                    warranty_id=None,
                    failure_keywords=failure_keywords,
                )
        except Exception as exc:
            log_action("review_peer_signal_fail", str(exc))

    # RAG indexing (if enabled)
    try:
        from .rag import add_event_documents, rag_enabled
        if rag_enabled():
            rows = (
                db.query(ProductReviewDB)
                .order_by(ProductReviewDB.created_at.desc())
                .limit(200)
                .all()
            )
            for r in rows:
                add_event_documents(
                    db,
                    doc_type="review",
                    doc_id=f"review:{r.id}",
                    content=f"brand={r.brand} model={r.model_code} region={r.region} rating={r.rating} sentiment={r.sentiment} text={r.text}",
                    metadata={
                        "brand": r.brand,
                        "model_code": r.model_code,
                        "region": r.region,
                        "source": r.source,
                    },
                )
    except Exception:
        pass

    return {"pages": pages_crawled, "reviews": reviews_added}


def crawl_reviews_for_product(
    db: Session,
    *,
    brand: str,
    product_name: Optional[str] = None,
    model_code: Optional[str] = None,
    region: str = "IN",
    max_pages: int = 5,
) -> Dict[str, int]:
    sources = load_review_sources()
    if not sources:
        return {"pages": 0, "reviews": 0}
    seed = ProductSeed(brand=brand, model_code=model_code, product_name=product_name or "", region=region)

    max_queries = int(os.getenv("REVIEW_MAX_QUERIES_PER_PRODUCT", "5"))
    max_results = int(os.getenv("REVIEW_MAX_RESULTS_PER_QUERY", "5"))
    max_pages_per_domain = int(os.getenv("REVIEW_MAX_PAGES_PER_DOMAIN", "10"))
    ttl_hours = int(os.getenv("REVIEW_CRAWL_TTL_HOURS", "24"))

    robots_cache: Dict[str, robotparser.RobotFileParser] = {}
    domain_counts: Dict[str, int] = {}
    pages_crawled = 0
    reviews_added = 0
    now = datetime.utcnow()

    for source in sources:
        if pages_crawled >= max_pages:
            break
        if source.get("region") not in (None, "", "*", seed.region, region):
            continue
        domains = source.get("domains") or []
        if not domains:
            continue
        queries = _build_queries(seed, domains)[:max_queries]
        for q in queries:
            if pages_crawled >= max_pages:
                break
            results = search_web(
                q,
                count=max_results,
                provider=os.getenv("REVIEW_SEARCH_PROVIDER", None),
                timeout=int(os.getenv("REVIEW_SEARCH_TIMEOUT_SEC", "8")),
            )
            for res in results:
                url = res.get("url") or ""
                if not url:
                    continue
                if not _allowed_domain(url, domains):
                    continue
                host = urlparse(url).netloc.lower()
                if domain_counts.get(host, 0) >= max_pages_per_domain:
                    continue
                if not _robots_allowed(url, robots_cache):
                    continue
                existing = db.query(ReviewPageDB).filter_by(url=url).first()
                if existing and existing.fetched_at and existing.fetched_at >= (now - timedelta(hours=ttl_hours)):
                    continue
                html, err, status = _fetch(url)
                domain_counts[host] = domain_counts.get(host, 0) + 1
                page = existing or ReviewPageDB(url=url)
                page.source = source.get("name")
                page.product_key = seed.key
                page.http_status = status
                page.last_error = err
                if html:
                    page.content_type = "text/html"
                    page.text_excerpt = _normalize_whitespace(html)[:800]
                    snapshot_uri = put_bytes(
                        html.encode("utf-8"),
                        key=f"reviews/{_hash_url(url)}.html",
                        content_type="text/html",
                    )
                    page.snapshot_uri = snapshot_uri
                    page.fetched_at = datetime.utcnow()
                    reviews, rating = _extract_reviews(html)
                    for text in reviews:
                        sentiment, _, _ = analyze_sentiment(text)
                        rec = ProductReviewDB(
                            brand=seed.brand,
                            model_code=seed.model_code,
                            product_type=None,
                            region=seed.region,
                            source=source.get("name"),
                            url=url,
                            rating=rating,
                            sentiment=sentiment,
                            text=text[:4000],
                        )
                        db.add(rec)
                        reviews_added += 1
                    pages_crawled += 1
                    log_action("review_page_fetched", f"url={url} reviews={len(reviews)}")
                if not existing:
                    db.add(page)
                db.commit()
                time.sleep(float(os.getenv("REVIEW_CRAWL_DELAY_SEC", "0.5")))

    # RAG indexing (if enabled)
    try:
        from .rag import add_event_documents, rag_enabled
        if rag_enabled():
            rows = (
                db.query(ProductReviewDB)
                .order_by(ProductReviewDB.created_at.desc())
                .limit(100)
                .all()
            )
            for r in rows:
                add_event_documents(
                    db,
                    doc_type="review",
                    doc_id=f"review:{r.id}",
                    content=f"brand={r.brand} model={r.model_code} region={r.region} rating={r.rating} sentiment={r.sentiment} text={r.text}",
                    metadata={
                        "brand": r.brand,
                        "model_code": r.model_code,
                        "region": r.region,
                        "source": r.source,
                    },
                )
    except Exception:
        pass

    return {"pages": pages_crawled, "reviews": reviews_added}


def _extract_failure_keywords(rows: List[ProductReviewDB]) -> List[str]:
    keywords = []
    for r in rows:
        text = (r.text or "").lower()
        for kw in ["broken", "leak", "noise", "overheat", "error", "fault", "dead", "smell", "burn"]:
            if kw in text:
                keywords.append(kw)
    # unique keep order
    seen = set()
    out = []
    for kw in keywords:
        if kw not in seen:
            seen.add(kw)
            out.append(kw)
    return out[:10]
