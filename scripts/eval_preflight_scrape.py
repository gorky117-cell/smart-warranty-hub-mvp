"""Evaluate preflight + scraping (terms discovery/lookup) on 50 synthetic cases.

This script is deterministic and does not depend on external search/API keys.
It monkeypatches discovery/search/parser functions during runtime to stress-test:
  preflight domain gating, source discovery, parser fallback, and default fallback.

Outputs:
  - data/preflight_scrape_eval_50.json (default)
  - test_data/preflight_scrape_cases_50.json
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from urllib.parse import urlparse

sys.path.insert(0, os.path.abspath("."))


# Configure env before importing modules that read constants at import-time.
os.environ.setdefault("TERMS_SCRAPE_ENABLED", "1")
os.environ.setdefault("TERMS_SCRAPE_MODE", "auto+manual")
os.environ.setdefault("TERMS_SCRAPE_ALLOW_RETAIL", "1")
os.environ.setdefault("TERMS_SEARCH_MAX_QUERIES", "2")
os.environ.setdefault("TERMS_SEARCH_MAX_RESULTS", "5")
os.environ.setdefault("TERMS_PREFLIGHT_STRICT", "true")
os.environ.setdefault("TERMS_ALLOW_BROAD_FALLBACK", "false")


@dataclass
class ProductTemplate:
    brand: str
    category: str
    domain: str
    product_name: str
    duration_months: int


PRODUCTS: List[ProductTemplate] = [
    ProductTemplate("Samsung", "mobile", "samsung.com", "Galaxy S24", 12),
    ProductTemplate("Apple", "mobile", "apple.com", "iPhone 15", 12),
    ProductTemplate("Sony", "electronics", "sony.com", "BRAVIA-X90", 24),
    ProductTemplate("LG", "electronics", "lg.com", "OLED55C3", 24),
    ProductTemplate("Whirlpool", "appliance", "whirlpool.com", "WM-8KG-PRO", 24),
    ProductTemplate("Bosch", "appliance", "bosch.com", "FR-320L-INV", 24),
    ProductTemplate("Ather", "ev", "atherenergy.com", "450X-BATT", 36),
    ProductTemplate("Tata", "ev", "tatamotors.com", "NEXON-EV-BATT", 36),
]


def _args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Evaluate preflight + scraping pipeline")
    p.add_argument("--rows", type=int, default=50, help="Number of synthetic cases")
    p.add_argument("--out", default="data/preflight_scrape_eval_50.json", help="Output JSON report path")
    p.add_argument(
        "--cases-out",
        default="test_data/preflight_scrape_cases_50.json",
        help="Output synthetic case definitions path",
    )
    p.add_argument(
        "--db",
        default="data/preflight_eval.db",
        help="SQLite DB file to use for isolated terms cache writes",
    )
    return p.parse_args()


def _percent(n: float, d: float) -> float:
    if d <= 0:
        return 0.0
    return round((n / d) * 100.0, 2)


def _percentile(values: List[float], q: float) -> float:
    if not values:
        return 0.0
    v = sorted(values)
    if len(v) == 1:
        return v[0]
    pos = q * (len(v) - 1)
    lo = int(pos)
    hi = min(lo + 1, len(v) - 1)
    frac = pos - lo
    return v[lo] * (1.0 - frac) + v[hi] * frac


def _host(url: Optional[str]) -> str:
    if not url:
        return ""
    try:
        return (urlparse(url).hostname or "").lower()
    except Exception:
        return ""


def _build_cases(rows: int) -> List[Dict[str, object]]:
    cases: List[Dict[str, object]] = []
    for i in range(1, rows + 1):
        prod = PRODUCTS[(i - 1) % len(PRODUCTS)]
        model_code = f"SWH-{i:04d}"
        region = "IN-KA" if i % 2 else "US-CA"
        scenario = "alive_success"
        if i > int(rows * 0.64) and i <= int(rows * 0.76):
            scenario = "dead_default"
        elif i > int(rows * 0.76) and i <= int(rows * 0.88):
            scenario = "no_brand_broad"
        elif i > int(rows * 0.88):
            scenario = "parse_failover"

        brand = prod.brand
        domain = prod.domain
        if scenario == "no_brand_broad":
            brand = ""

        primary_url = f"https://{domain}/support/warranty/{model_code.lower()}"
        backup_url = f"https://{domain}/support/warranty/backup/{model_code.lower()}"
        broad_url = f"https://docs.example.net/warranty/{model_code.lower()}"

        expected_source = "default" if scenario == "dead_default" else "scraped"
        expected_duration = 12 if scenario == "dead_default" else prod.duration_months
        if scenario == "dead_default" and prod.category == "ev":
            expected_duration = 36
        elif scenario == "dead_default" and prod.category == "appliance":
            expected_duration = 24
        elif scenario == "dead_default" and prod.category == "electronics":
            expected_duration = 12
        elif scenario == "dead_default" and prod.category == "mobile":
            expected_duration = 12

        cases.append(
            {
                "case_id": f"C{i:03d}",
                "scenario": scenario,
                "brand": brand,
                "domain": domain,
                "category": prod.category,
                "product_name": prod.product_name,
                "model_code": model_code,
                "region": region,
                "duration_months": prod.duration_months,
                "primary_url": primary_url,
                "backup_url": backup_url,
                "broad_url": broad_url,
                "expected_source": expected_source,
                "expected_duration": expected_duration,
            }
        )
    return cases


def main() -> int:
    args = _args()
    out_path = Path(args.out)
    cases_out_path = Path(args.cases_out)
    db_path = Path(args.db)

    # Isolated DB for this evaluation run.
    db_path.parent.mkdir(parents=True, exist_ok=True)
    if db_path.exists():
        db_path.unlink()
    os.environ["DATABASE_URL"] = f"sqlite:///{db_path.as_posix()}"

    from app.db import Base, SessionLocal, engine  # noqa: E402
    import app.db_models as _db_models  # noqa: F401, E402
    from app.services import terms_lookup  # noqa: E402
    from app.services import warranty_discovery as wd  # noqa: E402
    from app.services.warranty_parser import ParsedTerms  # noqa: E402

    Base.metadata.create_all(bind=engine)

    cases = _build_cases(args.rows)
    cases_out_path.parent.mkdir(parents=True, exist_ok=True)
    cases_out_path.write_text(json.dumps(cases, indent=2), encoding="utf-8")

    oem_domains: Dict[str, List[str]] = {}
    for p in PRODUCTS:
        oem_domains.setdefault(p.brand, [])
        if p.domain not in oem_domains[p.brand]:
            oem_domains[p.brand].append(p.domain)
    verified_domains: Dict[str, List[str]] = {
        "Samsung": ["samsung.com"],
        "Apple": ["apple.com"],
        "Sony": ["sony.com"],
        "LG": ["lg.com"],
    }

    state: Dict[str, object] = {
        "active_case": None,
        "query_log": [],
        "parse_attempts": [],
        "url_payloads": {},
    }

    def fake_load_oem_domains() -> Dict[str, List[str]]:
        return oem_domains

    def fake_load_verified_domains() -> Dict[str, List[str]]:
        return verified_domains

    def fake_domain_alive(domain: str, timeout: int) -> bool:
        active = state.get("active_case") or {}
        scenario = str(active.get("scenario") or "")
        expected_domain = str(active.get("domain") or "").lower()
        if not domain or domain.lower() != expected_domain:
            return False
        return scenario in ("alive_success", "parse_failover")

    def fake_search_web(query: str, count: int = 5, timeout: int = 6) -> List[Dict]:
        qlog = state["query_log"]
        assert isinstance(qlog, list)
        qlog.append(query)

        active = state.get("active_case") or {}
        scenario = str(active.get("scenario") or "")
        model_code = str(active.get("model_code") or "")
        domain = str(active.get("domain") or "")
        primary_url = str(active.get("primary_url") or "")
        backup_url = str(active.get("backup_url") or "")
        broad_url = str(active.get("broad_url") or "")

        if scenario == "dead_default":
            return []

        if "site:" in query:
            if f"site:{domain}" in query and model_code in query:
                if scenario == "parse_failover":
                    return [
                        {"url": primary_url, "title": "Official Warranty"},
                        {"url": backup_url, "title": "Official Backup Warranty"},
                        {"url": f"https://retail.example/{model_code.lower()}", "title": "Retail Listing"},
                    ][:count]
                return [
                    {"url": primary_url, "title": "Official Warranty"},
                    {"url": f"https://retail.example/{model_code.lower()}", "title": "Retail Listing"},
                ][:count]
            return []

        if scenario == "no_brand_broad":
            return [
                {"url": broad_url, "title": "Warranty Policy"},
                {"url": f"https://random.example/{model_code.lower()}", "title": "Community Post"},
            ][:count]

        # Fallback broad path (unexpected for strict preflight-known brand).
        return [{"url": primary_url, "title": "Warranty Policy"}][:count]

    def fake_parse_terms_from_url(url: str, timeout: int = 10) -> Tuple[Optional[ParsedTerms], Optional[str]]:
        patt = state["parse_attempts"]
        assert isinstance(patt, list)
        patt.append(url)

        active = state.get("active_case") or {}
        scenario = str(active.get("scenario") or "")
        model_code = str(active.get("model_code") or "")
        duration = int(active.get("duration_months") or 12)
        category = str(active.get("category") or "general")
        primary_url = str(active.get("primary_url") or "")

        if scenario == "parse_failover" and url == primary_url:
            return None, "Simulated primary parse failure"

        if not url.startswith("http"):
            return None, "Unsupported URL for synthetic parser"

        if scenario == "no_brand_broad" and "docs.example.net" not in _host(url):
            return None, "Noise source skipped"

        parsed = ParsedTerms(
            duration_months=duration,
            terms=[f"{category.title()} coverage for {duration} months for model {model_code}."],
            exclusions=["Accidental and liquid damage excluded."],
            claim_steps=["Keep invoice and serial number.", "Contact official support."],
            raw_text=f"Synthetic parsed terms for {model_code}",
            confidence=0.9,
        )
        return parsed, None

    # Monkeypatch runtime dependencies used by discovery/lookup.
    wd.load_oem_domains = fake_load_oem_domains  # type: ignore[assignment]
    wd.load_verified_domains = fake_load_verified_domains  # type: ignore[assignment]
    wd._domain_alive = fake_domain_alive  # type: ignore[assignment]
    wd.search_web = fake_search_web  # type: ignore[assignment]
    terms_lookup.discover_sources = wd.discover_sources  # type: ignore[assignment]
    terms_lookup.parse_terms_from_url = fake_parse_terms_from_url  # type: ignore[assignment]

    latencies_ms: List[float] = []
    case_results: List[Dict[str, object]] = []

    totals = {
        "lookup_success": 0,
        "source_expected_match": 0,
        "duration_exact_match": 0,
        "official_source_success": 0,
        "official_source_candidates": 0,
        "preflight_site_used": 0,
        "preflight_site_expected": 0,
        "strict_block_ok": 0,
        "strict_block_expected": 0,
        "failover_ok": 0,
        "failover_expected": 0,
        "parse_success": 0,
        "parse_attempts": 0,
    }

    with SessionLocal() as db:
        for case in cases:
            state["active_case"] = case
            state["query_log"] = []
            state["parse_attempts"] = []

            t0 = time.perf_counter()
            result = terms_lookup.lookup_terms(
                db,
                brand=(case["brand"] or None),
                category=str(case["category"]),
                region=str(case["region"]),
                model_code=str(case["model_code"]),
                product_name=str(case["product_name"]),
                force_refresh=True,
            )
            elapsed_ms = (time.perf_counter() - t0) * 1000.0
            latencies_ms.append(elapsed_ms)

            queries = list(state["query_log"]) if isinstance(state["query_log"], list) else []
            parse_attempts = list(state["parse_attempts"]) if isinstance(state["parse_attempts"], list) else []

            source_url = result.source_url or ""
            is_default = source_url == "internal://default_rules"
            source_kind = "default" if is_default else "scraped"
            expected_source = str(case["expected_source"])
            source_match = source_kind == expected_source

            expected_duration = int(case["expected_duration"])
            duration_match = int(result.duration_months or 0) == expected_duration

            brand = str(case["brand"] or "")
            domain = str(case["domain"] or "").lower()
            official_ok = False
            if brand and not is_default:
                totals["official_source_candidates"] += 1
                h = _host(source_url)
                official_ok = bool(h and (h == domain or h.endswith(f".{domain}")))
                if official_ok:
                    totals["official_source_success"] += 1

            scenario = str(case["scenario"])
            has_site_query = any(str(q).startswith("site:") for q in queries)
            has_broad_query = any(not str(q).startswith("site:") for q in queries)
            strict_block_ok = True
            if scenario == "dead_default":
                totals["strict_block_expected"] += 1
                strict_block_ok = (not has_broad_query) and is_default
                if strict_block_ok:
                    totals["strict_block_ok"] += 1

            if scenario in ("alive_success", "parse_failover"):
                totals["preflight_site_expected"] += 1
                if has_site_query:
                    totals["preflight_site_used"] += 1

            failover_ok = True
            if scenario == "parse_failover":
                totals["failover_expected"] += 1
                backup_url = str(case["backup_url"])
                failover_ok = len(parse_attempts) >= 2 and source_url == backup_url
                if failover_ok:
                    totals["failover_ok"] += 1

            parse_success = not is_default and bool(parse_attempts)
            totals["parse_attempts"] += len(parse_attempts)
            if parse_success:
                totals["parse_success"] += 1

            if not is_default:
                totals["lookup_success"] += 1
            if source_match:
                totals["source_expected_match"] += 1
            if duration_match:
                totals["duration_exact_match"] += 1

            case_results.append(
                {
                    "case_id": case["case_id"],
                    "scenario": scenario,
                    "source_url": source_url,
                    "source_kind": source_kind,
                    "expected_source": expected_source,
                    "source_match": source_match,
                    "duration_months": result.duration_months,
                    "expected_duration": expected_duration,
                    "duration_match": duration_match,
                    "official_source_ok": official_ok if brand else None,
                    "site_query_used": has_site_query,
                    "broad_query_used": has_broad_query,
                    "strict_block_ok": strict_block_ok if scenario == "dead_default" else None,
                    "failover_ok": failover_ok if scenario == "parse_failover" else None,
                    "search_queries": queries,
                    "parse_attempts": parse_attempts,
                    "latency_ms": round(elapsed_ms, 2),
                }
            )

    summary = {
        "dataset_rows": len(cases),
        "lookup_success_rate_pct": _percent(totals["lookup_success"], len(cases)),
        "source_expected_match_rate_pct": _percent(totals["source_expected_match"], len(cases)),
        "duration_exact_match_rate_pct": _percent(totals["duration_exact_match"], len(cases)),
        "official_source_rate_pct": _percent(totals["official_source_success"], totals["official_source_candidates"]),
        "preflight_site_query_usage_pct": _percent(totals["preflight_site_used"], totals["preflight_site_expected"]),
        "strict_preflight_block_accuracy_pct": _percent(totals["strict_block_ok"], totals["strict_block_expected"]),
        "parser_failover_success_pct": _percent(totals["failover_ok"], totals["failover_expected"]),
        "parse_success_per_case_pct": _percent(totals["parse_success"], len(cases)),
        "parse_success_per_attempt_pct": _percent(totals["parse_success"], totals["parse_attempts"]),
        "latency_p50_ms": round(_percentile(latencies_ms, 0.50), 2),
        "latency_p95_ms": round(_percentile(latencies_ms, 0.95), 2),
    }

    report = {
        "summary": summary,
        "scenarios": {
            "alive_success": len([c for c in cases if c["scenario"] == "alive_success"]),
            "dead_default": len([c for c in cases if c["scenario"] == "dead_default"]),
            "no_brand_broad": len([c for c in cases if c["scenario"] == "no_brand_broad"]),
            "parse_failover": len([c for c in cases if c["scenario"] == "parse_failover"]),
        },
        "artifacts": {
            "cases_file": str(cases_out_path).replace("\\", "/"),
            "db_file": str(db_path).replace("\\", "/"),
        },
        "cases": case_results,
    }

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    print("\n=== Preflight + Scraping KPI Summary ===")
    print(json.dumps(summary, indent=2))
    print(f"\nSaved report: {out_path}")
    print(f"Saved cases: {cases_out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
