"""Verify every domain in data/oem_domains.json with the app's domain verification.

Uses `oem_domain_verify.verify_domain_detail()` (fix run B8): registry mapping, DNS, HTTPS, same-brand
redirects, brand in <title>/metadata or a reachable same-brand support/warranty page. Also records an
India signal (`.in` domain, or https://<domain>/in/ reachable on an India path).

Politeness: 4 domains in parallel, a pause between requests, at most ~9 requests per domain.
Nothing is written unless --write-verified is given; then passing domains are merged into
data/oem_verified.json (existing entries kept).

Usage: python scripts/preflight_oem_registry.py --out data/oem_domain_preflight_<date>.json [--write-verified]
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import urlparse

import requests

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.services.oem_domain_verify import USER_AGENT, verify_domain_detail  # noqa: E402
from app.services.oem_domains import load_oem_domains, load_verified_domains, save_verified_domains  # noqa: E402

PAUSE_SEC = 0.5


def _india_signal(domain: str) -> str:
    if domain.endswith(".in"):
        return "india_domain"
    try:
        resp = requests.get(f"https://{domain}/in/", timeout=6, headers={"User-Agent": USER_AGENT}, allow_redirects=True)
    except requests.exceptions.RequestException:
        return "none"
    final = urlparse(resp.url)
    on_india = final.path.lower().startswith("/in") or (final.hostname or "").endswith(".in")
    return "india_path" if resp.status_code < 400 and on_india else "none"


def check(brand: str, domain: str) -> dict:
    detail = verify_domain_detail(brand, domain)
    time.sleep(PAUSE_SEC)
    detail["india"] = _india_signal(detail["domain"]) if detail.get("steps", {}).get("dns") == "ok" else "none"
    return detail


def main() -> None:
    parser = argparse.ArgumentParser(description="Verify the OEM domain registry")
    parser.add_argument("--out", required=True)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--write-verified", action="store_true")
    args = parser.parse_args()

    registry = load_oem_domains()
    jobs = [(brand, domain) for brand, domains in registry.items() for domain in domains]
    started = time.time()
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        results = list(pool.map(lambda job: check(*job), jobs))

    passing = {}
    for row in results:
        if row["verified"]:
            passing.setdefault(row["brand"], []).append(row["domain"])
    by_brand = {}
    for row in results:
        entry = by_brand.setdefault(row["brand"], {"verified": False, "india": set()})
        entry["verified"] |= bool(row["verified"])
        if row["india"] != "none":
            entry["india"].add(row["india"])
    summary = {
        "brands": len(registry),
        "domains": len(jobs),
        "domains_verified": sum(1 for r in results if r["verified"]),
        "brands_verified": sum(1 for e in by_brand.values() if e["verified"]),
        "reasons": dict(Counter(r.get("reason") for r in results)),
        "evidence": dict(Counter(r.get("steps", {}).get("brand_evidence") for r in results if r["verified"])),
        "brands_with_india_domain": sorted(b for b, e in by_brand.items() if "india_domain" in e["india"]),
        "brands_with_india_path_only": sorted(b for b, e in by_brand.items() if e["india"] == {"india_path"}),
        "elapsed_sec": round(time.time() - started, 1),
    }
    if args.write_verified:
        verified = load_verified_domains()
        for brand, domains in passing.items():
            merged = list(dict.fromkeys(list(verified.get(brand, [])) + domains))
            verified[brand] = merged
        save_verified_domains(dict(sorted(verified.items())))
        summary["written_to_verified_list"] = sum(len(v) for v in passing.values())
    Path(args.out).write_text(json.dumps({"summary": summary, "passing": passing, "results": results}, indent=1), encoding="utf-8")
    print(json.dumps(summary, indent=1))


if __name__ == "__main__":
    main()
