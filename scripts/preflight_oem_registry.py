"""Read-only preflight of every domain in data/oem_domains.json.

For each brand/domain it runs the app's own checks without saving anything:
  1. `warranty_discovery._domain_alive()`  - DNS + HTTP(S) status < 500 (what terms discovery uses).
  2. `oem_domain_verify._verify_domain()`  - homepage fetch, brand name and a support keyword present
     (what would be written to data/oem_verified.json; NOT written here).
  3. India signal - `.in` domain, else GET https://<domain>/in/ and accept status < 400 when the final
     URL stays on an India path or `.in` host.

Politeness: at most 3 requests per domain, 4 domains in parallel, a pause between requests.

Usage: python scripts/preflight_oem_registry.py --out data/oem_domain_preflight_<date>.json
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

from app.services.oem_domain_verify import _verify_domain  # noqa: E402
from app.services.oem_domains import load_oem_domains  # noqa: E402
from app.services.warranty_discovery import _domain_alive  # noqa: E402

PAUSE_SEC = 0.5
TIMEOUT_SEC = 6
USER_AGENT = "SmartWarrantyHub/1.0"


def _india_signal(domain: str) -> str:
    if domain.endswith(".in"):
        return "india_domain"
    try:
        resp = requests.get(
            f"https://{domain}/in/", timeout=TIMEOUT_SEC, headers={"User-Agent": USER_AGENT}, allow_redirects=True
        )
    except requests.exceptions.RequestException:
        return "none"
    final = urlparse(resp.url)
    on_india = final.path.lower().startswith(("/in/", "/in")) or (final.hostname or "").endswith(".in")
    return "india_path" if resp.status_code < 400 and on_india else "none"


def check(brand: str, domain: str) -> dict:
    alive = _domain_alive(domain, timeout=TIMEOUT_SEC)
    time.sleep(PAUSE_SEC)
    if alive:
        verified, reason = _verify_domain(brand, domain)
        time.sleep(PAUSE_SEC)
        india = _india_signal(domain)
    else:
        verified, reason, india = False, "not_alive", "none"
    return {"brand": brand, "domain": domain, "alive": alive, "would_verify": verified, "reason": reason, "india": india}


def main() -> None:
    parser = argparse.ArgumentParser(description="Read-only preflight of the OEM domain registry")
    parser.add_argument("--out", required=True)
    parser.add_argument("--workers", type=int, default=4)
    args = parser.parse_args()

    registry = load_oem_domains()
    jobs = [(brand, domain) for brand, domains in registry.items() for domain in domains]
    started = time.time()
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        results = list(pool.map(lambda job: check(*job), jobs))

    by_brand = {}
    for row in results:
        entry = by_brand.setdefault(row["brand"], {"alive": False, "would_verify": False, "india": set()})
        entry["alive"] |= row["alive"]
        entry["would_verify"] |= row["would_verify"]
        if row["india"] != "none":
            entry["india"].add(row["india"])
    summary = {
        "brands": len(registry),
        "domains": len(jobs),
        "domains_alive": sum(r["alive"] for r in results),
        "domains_would_verify": sum(r["would_verify"] for r in results),
        "domain_reasons": dict(Counter(r["reason"] for r in results)),
        "brands_alive": sum(e["alive"] for e in by_brand.values()),
        "brands_would_verify": sum(e["would_verify"] for e in by_brand.values()),
        "brands_with_india_domain": sorted(b for b, e in by_brand.items() if "india_domain" in e["india"]),
        "brands_with_india_path_only": sorted(b for b, e in by_brand.items() if e["india"] == {"india_path"}),
        "elapsed_sec": round(time.time() - started, 1),
    }
    report = {"_note": "Read-only preflight; nothing written to data/oem_verified.json.", "summary": summary, "results": results}
    Path(args.out).write_text(json.dumps(report, indent=1), encoding="utf-8")
    print(json.dumps(summary, indent=1))


if __name__ == "__main__":
    main()
