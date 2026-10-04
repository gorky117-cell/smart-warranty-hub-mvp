"""Send every invoice in real_invoices/ through the full upload pipeline; write review.md (always) and report.md.

Real invoices, expected values, review marks, reports and corrections stay in real_invoices/, which is
git-ignored: never commit them.

    python scripts/run_real_invoices.py [--dir real_invoices] [--provider auto|openai|mistral|both]
                                        [--offline] [--no-ai] [--no-vision]

- Runs the real app in-process (POST /artifacts/upload, as a browser upload does) against a throwaway SQLite
  database, so nothing is written to the app's own database or data/ files.
- review.md (always): per file, what SWH read - text engine and characters, brand, model, serial, invoice
  number, date, category, OEM website, warranty duration and source URL, the estimated / please-confirm
  status and the first lines of the customer summary - with blank "OK?" and "Correct value if wrong"
  columns. Mark them by hand (y / n / ?) and re-run: marks become pass / fail counts per stage. A mark is
  kept while SWH's value is unchanged.
- expected.csv is optional. Where it has values, report.md also scores each stage automatically.
- AI is on only when keys are present in the local .env (or the environment); key values are never printed
  or written anywhere. --provider auto uses whatever keys exist with the app's normal OpenAI<->Mistral
  fallback; openai or mistral runs that provider alone (fallback off); both runs each alone, in separate
  processes, and report.md compares field accuracy, warranty page reading, time and API cost. The vision
  tier for unreadable photos is OpenAI-only.
- --offline blocks all non-loopback network (no OEM website lookups or AI calls); used by the tests.
- API cost: calls and tokens are counted; a cost is shown only when prices are set in the environment
  (USD per 1M tokens): COST_OPENAI_INPUT, COST_OPENAI_OUTPUT, COST_MISTRAL_INPUT, COST_MISTRAL_OUTPUT.

expected.csv columns: file, brand, model, serial, invoice_no, purchase_date, category, warranty_months,
key_exclusions (separated by ";"), oem_url. Blank expected values are not judged.

Outcomes per stage: pass; confirm (the app asks the customer to confirm - acceptable); missing (nothing
shown - not acceptable, not wrong); fail (a confident wrong value); n/a (no expected value to judge).
"""
from __future__ import annotations

import argparse
import csv
import os
import json
import secrets
import subprocess
import sys
import tempfile
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
EXPECTED_COLUMNS = [
    "file", "brand", "model", "serial", "invoice_no", "purchase_date", "category", "warranty_months",
    "key_exclusions", "oem_url",
]
INVOICE_SUFFIXES = {".pdf", ".png", ".jpg", ".jpeg", ".webp", ".tif", ".tiff", ".bmp", ".docx", ".txt"}
ACCEPTABLE = ("pass", "confirm")
STAGES = ("text", "fields", "oem_domain", "warranty_page", "duration", "exclusions", "summary")


# --- environment (must run before the app is imported) -----------------------------------------------


def _read_env_file(path: Path) -> Dict[str, str]:
    values: Dict[str, str] = {}
    if not path.exists():
        return values
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip().removeprefix("export ").strip()
        values[key] = value.strip().strip('"').strip("'")
    return values


class ProviderUnavailable(RuntimeError):
    pass


def configure_environment(*, offline: bool, no_ai: bool, no_vision: bool, provider: str = "auto") -> Dict[str, Any]:
    """Isolated DB, AI only when keys exist, generated admin login. Returns what was enabled (no values).

    provider: "auto" (whatever keys exist, with the app's normal OpenAI<->Mistral fallback), or "openai" /
    "mistral" (that provider only for invoice enrichment, terms extraction and summaries; fallback off)."""
    for key, value in _read_env_file(ROOT / ".env").items():
        os.environ.setdefault(key, value)
    from importlib.util import find_spec

    openai_package = find_spec("openai") is not None
    if provider in ("openai", "mistral") and not no_ai:
        key_name = "OPENAI_API_KEY" if provider == "openai" else "MISTRAL_API_KEY"
        if not os.getenv(key_name):
            raise ProviderUnavailable(f"{key_name} is not in the local .env or environment; cannot run --provider {provider}")
        if provider == "openai" and not openai_package:
            raise ProviderUnavailable("the 'openai' package is not installed here (pip install -r requirements.txt); cannot run --provider openai")
    if os.getenv("OPENAI_API_KEY") and not openai_package and not no_ai:
        print("Note: OPENAI_API_KEY is set but the 'openai' package is not installed; OpenAI is off for this run.")
        os.environ.pop("OPENAI_API_KEY", None)
    tmp = Path(tempfile.mkdtemp(prefix="swh_real_invoices_"))
    os.environ["DATABASE_URL"] = f"sqlite:///{(tmp / 'run.db').as_posix()}"
    os.environ["AI_QUOTA_FILE"] = str(tmp / "ai_quota.json")
    os.environ["ADMIN_USER"] = "real_invoice_runner"
    os.environ["ADMIN_PASS"] = secrets.token_urlsafe(18)
    os.environ["ALLOW_INSECURE_DEFAULTS"] = "false"
    os.environ.setdefault("JWT_SECRET", secrets.token_urlsafe(48))
    os.environ.setdefault("JWT_SALT", secrets.token_urlsafe(16))
    os.environ["SCHEDULER_ENABLED"] = "0"
    os.environ["OEM_AUTO_VERIFY"] = "false"  # would write data/oem_verified.json
    os.environ["RAG_ENABLED"] = "0"
    os.environ["EMAIL_ENABLED"] = "false"
    os.environ["RATE_LIMIT_ENABLED"] = "0"
    os.environ["OCR_WARMUP"] = "0"
    has_openai = bool(os.getenv("OPENAI_API_KEY")) and not no_ai and provider != "mistral"
    has_mistral = bool(os.getenv("MISTRAL_API_KEY")) and not no_ai and provider != "openai"
    os.environ["OPENAI_ENABLED"] = "1" if has_openai else "0"
    os.environ["OPENAI_INVOICE_ENRICHMENT"] = "1" if has_openai else "0"
    os.environ["AI_INVOICE_ENRICHMENT"] = "1" if (has_openai or has_mistral) else "0"
    # The vision tier is OpenAI-only in the code today.
    os.environ["VISION_AI_EXTRACTION"] = "1" if has_openai and not no_vision else "0"
    os.environ["LLM_PROVIDER"] = "openai" if has_openai else ("mistral" if has_mistral else "none")
    if provider in ("openai", "mistral"):
        os.environ["AI_PROVIDER"] = provider
        os.environ["AI_PROVIDER_FALLBACK"] = "0"  # measure one provider at a time
    if not has_openai:
        os.environ.pop("OPENAI_API_KEY", None)
    if not has_mistral:
        os.environ.pop("MISTRAL_API_KEY", None)
    if offline:
        _block_network()
    return {
        "provider": provider if provider in ("openai", "mistral") else "auto",
        "openai": has_openai, "mistral": has_mistral, "vision": has_openai and not no_vision, "offline": offline,
    }


def _block_network() -> None:
    import socket

    real_connect, real_getaddrinfo = socket.socket.connect, socket.getaddrinfo

    def local(host: Any) -> bool:
        host = str(host or "")
        return host in ("localhost", "::1", "testserver") or host.startswith("127.")

    def connect(sock, address):
        host = address[0] if isinstance(address, tuple) else address
        if not local(host):
            raise OSError(f"network disabled (--offline): {host}")
        return real_connect(sock, address)

    def getaddrinfo(host, *args, **kwargs):
        if host and not local(host):
            raise socket.gaierror(f"network disabled (--offline): {host}")
        return real_getaddrinfo(host, *args, **kwargs)

    socket.socket.connect = connect
    socket.getaddrinfo = getaddrinfo


# --- API usage accounting ------------------------------------------------------------------------------


class Usage:
    def __init__(self) -> None:
        self.calls: Counter = Counter()
        self.tokens: Dict[str, Counter] = defaultdict(Counter)

    def snapshot(self) -> Tuple[Counter, Dict[str, Counter]]:
        return Counter(self.calls), {k: Counter(v) for k, v in self.tokens.items()}

    def since(self, snap) -> Dict[str, Dict[str, int]]:
        calls, tokens = snap
        out: Dict[str, Dict[str, int]] = {}
        for provider in set(self.calls) | set(self.tokens):
            out[provider] = {
                "calls": self.calls[provider] - calls.get(provider, 0),
                "input_tokens": self.tokens[provider]["input"] - tokens.get(provider, Counter())["input"],
                "output_tokens": self.tokens[provider]["output"] - tokens.get(provider, Counter())["output"],
            }
        return {k: v for k, v in out.items() if v["calls"]}


USAGE = Usage()


def _install_usage_hooks() -> None:
    import requests

    from app.services import openai_intelligence

    real_get_client = openai_intelligence._get_client

    class _Responses:
        def __init__(self, inner):
            self._inner = inner

        def create(self, *args, **kwargs):
            USAGE.calls["openai"] += 1
            response = self._inner.create(*args, **kwargs)
            usage = getattr(response, "usage", None)
            USAGE.tokens["openai"]["input"] += int(getattr(usage, "input_tokens", 0) or 0)
            USAGE.tokens["openai"]["output"] += int(getattr(usage, "output_tokens", 0) or 0)
            return response

    class _Client:
        def __init__(self, inner):
            self._inner = inner
            self.responses = _Responses(inner.responses)

        def __getattr__(self, name):
            return getattr(self._inner, name)

    def counted_client():
        client, err = real_get_client()
        return (_Client(client) if client is not None else None), err

    openai_intelligence._get_client = counted_client

    real_post = requests.post

    def counted_post(url, *args, **kwargs):
        if "mistral.ai" in str(url):
            USAGE.calls["mistral"] += 1  # counted when attempted, like OpenAI
        response = real_post(url, *args, **kwargs)
        if "mistral.ai" in str(url):
            try:
                usage = response.json().get("usage") or {}
                USAGE.tokens["mistral"]["input"] += int(usage.get("prompt_tokens") or 0)
                USAGE.tokens["mistral"]["output"] += int(usage.get("completion_tokens") or 0)
            except Exception:
                pass
        return response

    requests.post = counted_post


def _cost(usage: Dict[str, Dict[str, int]]) -> Optional[float]:
    total, priced = 0.0, False
    for provider, u in usage.items():
        inp, out = os.getenv(f"COST_{provider.upper()}_INPUT"), os.getenv(f"COST_{provider.upper()}_OUTPUT")
        if not inp or not out:
            return None
        priced = True
        total += u["input_tokens"] / 1e6 * float(inp) + u["output_tokens"] / 1e6 * float(out)
    return round(total, 4) if priced else 0.0


# --- judging ---------------------------------------------------------------------------------------------


def _norm(value: Any) -> str:
    return " ".join(str(value or "").lower().split())


def _norm_code(value: Any) -> str:
    return "".join(ch for ch in str(value or "").upper() if ch.isalnum())


def _host(url: Optional[str]) -> str:
    raw = (url or "").strip()
    if not raw:
        return ""
    host = (urlparse(raw if "://" in raw else f"https://{raw}").hostname or "").lower()
    return host[4:] if host.startswith("www.") else host


def _host_matches(host: str, domain: str) -> bool:
    return bool(host and domain) and (host == domain or host.endswith(f".{domain}") or domain.endswith(f".{host}"))


def judge_field(field: str, expected: str, stored: Any, suggestion: Optional[dict]) -> str:
    from app.services.ingestion import parse_date_from_text

    if not str(expected or "").strip():
        return "n/a"
    if field == "purchase_date":
        same = lambda a, b: (parse_date_from_text(str(a)) or _norm(a)) == (parse_date_from_text(str(b)) or _norm(b))  # noqa: E731
    elif field in ("model", "serial", "invoice_no"):
        same = lambda a, b: _norm_code(a) == _norm_code(b)  # noqa: E731
    else:
        same = lambda a, b: _norm(a) == _norm(b)  # noqa: E731
    if stored:
        return "pass" if same(stored, expected) else "fail"
    if suggestion and suggestion.get("status") == "pending":
        return "confirm"
    return "missing"


def _combine(outcomes: List[str]) -> str:
    judged = [o for o in outcomes if o != "n/a"]
    if not judged:
        return "n/a"
    for level in ("fail", "missing", "confirm"):
        if level in judged:
            return level
    return "pass"


def evaluate(path: Path, expected: Dict[str, str], client, auth: Dict[str, str]) -> Dict[str, Any]:
    from app.db import SessionLocal
    from app.db_models import ArtifactDB, PipelineJobDB, WarrantyDB
    from app.services.brand_families import resolve_oem_entity
    from app.services.oem_domains import load_manual_confirmed_domains, load_oem_domains, load_verified_domains
    from app.services.product_recommendations import infer_product_category

    row: Dict[str, Any] = {"file": path.name, "stages": {}, "causes": []}
    snap = USAGE.snapshot()
    started = time.perf_counter()
    with path.open("rb") as fh:
        resp = client.post(
            "/artifacts/upload",
            files={"file": (path.name, fh, "application/octet-stream")},
            data={"type": "invoice", "force_process": "true"},
            headers=auth,
        )
    row["seconds"] = round(time.perf_counter() - started, 1)
    row["usage"] = USAGE.since(snap)
    row["cost_usd"] = _cost(row["usage"])
    body = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else {}
    wid = body.get("warranty_id")
    if resp.status_code >= 400 or not wid:
        row["error"] = f"upload {resp.status_code}: {str(body.get('detail') or '')[:120]}"
        row["causes"].append("upload_rejected")
        for stage in STAGES:
            row["stages"][stage] = "fail"
        row["review"] = {"text": f"upload rejected ({row['error']})"}
        return row

    with SessionLocal() as db:
        w = db.query(WarrantyDB).filter_by(id=wid).first()
        job = db.query(PipelineJobDB).filter_by(warranty_id=wid).order_by(PipelineJobDB.updated_at.desc()).first()
        artifact_ids = list(w.source_artifact_ids or [])
        art = db.query(ArtifactDB).filter_by(id=artifact_ids[0]).first() if artifact_ids else None
        content = (art.content if art else "") or ""
        alt = dict(w.alternatives or {})
        stored = {
            "brand": w.brand, "model": w.model_code, "serial": w.serial_no, "product": w.product_name,
            "purchase_date": w.purchase_date.date().isoformat() if w.purchase_date else None,
            "coverage_months": w.coverage_months, "exclusions": list(w.exclusions or []),
        }
    parsed = client.get(f"/warranties/{wid}", headers=auth).json()
    summary = client.get(f"/warranties/{wid}/summary", headers=auth)
    summary_json = summary.json() if summary.status_code == 200 else {}
    evidence = parsed.get("evidence_status") or {}
    row["job"] = f"{job.status if job else '?'}{(' / ' + job.error) if job and job.error else ''}"

    # 1) text read
    ocr = alt.get("ocr") or {}
    text_chars = len(content.split("[OCR note]")[0].strip())
    row["text"] = {"engine": ocr.get("engine") or ocr.get("method") or "text", "method": ocr.get("method"), "chars": text_chars}
    row["stages"]["text"] = "pass" if text_chars >= 60 else ("confirm" if alt.get("unreadable_invoice") else "fail")
    if row["stages"]["text"] != "pass":
        row["causes"].append("text_not_read" if text_chars < 60 else "text_short")

    # 2) fields vs expected
    invoice_no = None
    with SessionLocal() as db:
        from app.db_models import ParsedFieldDB

        pf = db.query(ParsedFieldDB).filter_by(warranty_id=wid).order_by(ParsedFieldDB.created_at.desc()).first()
        invoice_no = pf.invoice_no if pf else None
        coarse_category = pf.product_category if pf else None
    fine_category = infer_product_category({"product_name": stored["product"], "model_code": stored["model"]})
    field_outcomes = {
        "brand": judge_field("brand", expected.get("brand"), stored["brand"], alt.get("brand_suggestion")),
        "model": judge_field("model", expected.get("model"), stored["model"], alt.get("model_suggestion")),
        "serial": judge_field("serial", expected.get("serial"), stored["serial"], alt.get("serial_suggestion")),
        "invoice_no": judge_field("invoice_no", expected.get("invoice_no"), invoice_no, None),
        "purchase_date": judge_field("purchase_date", expected.get("purchase_date"), stored["purchase_date"], None),
    }
    exp_cat = _norm(expected.get("category"))
    field_outcomes["category"] = "n/a" if not exp_cat else (
        "pass" if exp_cat in {_norm(coarse_category), _norm(fine_category)} else ("missing" if not (coarse_category or fine_category) else "fail")
    )
    row["fields"] = {
        "values": {**{k: stored[k] for k in ("brand", "model", "serial", "purchase_date")}, "invoice_no": invoice_no,
                   "category": f"{coarse_category or '-'} / {fine_category}", "product": stored["product"]},
        "suggestions": {k: (alt.get(f"{k}_suggestion") or {}).get("value") for k in ("brand", "model", "serial") if alt.get(f"{k}_suggestion")},
        "outcomes": field_outcomes,
    }
    row["stages"]["fields"] = _combine(list(field_outcomes.values()))
    row["causes"] += [f"field_{o}:{f}" for f, o in field_outcomes.items() if o in ("fail", "missing")]

    # 3) brand -> OEM domain
    entity = alt.get("oem_entity") or {}
    company = entity.get("company") if entity else stored["brand"]
    if not entity and stored["brand"]:
        company = resolve_oem_entity(stored["brand"], product_name=stored["product"], model_code=stored["model"]).company
    domains: List[str] = []
    for registry in (load_oem_domains(), load_verified_domains(), load_manual_confirmed_domains()):
        for name, hosts in registry.items():
            if company and name.lower() == str(company).lower():
                domains += [h for h in hosts if h not in domains]
    expected_host = _host(expected.get("oem_url"))
    row["oem"] = {"company": company, "domains": domains, "expected_host": expected_host or None}
    if not expected_host:
        row["stages"]["oem_domain"] = "n/a"
    elif not domains:
        row["stages"]["oem_domain"] = "confirm" if not stored["brand"] and alt.get("brand_suggestion") else "missing"
    else:
        row["stages"]["oem_domain"] = "pass" if any(_host_matches(expected_host, d) for d in domains) else "fail"
    if row["stages"]["oem_domain"] in ("fail", "missing"):
        row["causes"].append("oem_domain_wrong" if row["stages"]["oem_domain"] == "fail" else "oem_domain_not_found")

    # 4) warranty page found and read
    source_url = alt.get("terms_source_url") or ""
    source_type = alt.get("terms_source_type") or "-"
    page_host = _host(source_url) if source_url.startswith("http") else ""
    row["page"] = {"url": source_url or None, "type": source_type}
    if not page_host:
        row["stages"]["warranty_page"] = "confirm" if source_type in ("needs_check", "unreadable") else "missing"
    elif expected_host:
        row["stages"]["warranty_page"] = "pass" if _host_matches(page_host, expected_host) else "fail"
    else:
        row["stages"]["warranty_page"] = "pass" if source_type == "approved_oem_source" or evidence.get("source_trust", {}).get("official") else "fail"
    if row["stages"]["warranty_page"] in ("fail", "missing"):
        row["causes"].append("warranty_page_wrong" if row["stages"]["warranty_page"] == "fail" else "warranty_page_not_found")

    # 5) duration and exclusions
    exp_months = str(expected.get("warranty_months") or "").strip()
    shown = stored["coverage_months"]
    row["duration"] = {"shown": shown, "expected": exp_months or None}
    if not exp_months:
        row["stages"]["duration"] = "n/a"
    elif shown is None:
        row["stages"]["duration"] = "confirm" if source_type in ("needs_check", "unreadable") else "missing"
    else:
        row["stages"]["duration"] = "pass" if int(shown) == int(float(exp_months)) else "fail"
    if row["stages"]["duration"] == "fail":
        row["causes"].append("duration_wrong_estimated" if evidence.get("status") in ("estimated", "not_confirmed") else "duration_wrong")
    elif row["stages"]["duration"] == "missing":
        row["causes"].append("duration_missing")
    keywords = [k.strip().lower() for k in str(expected.get("key_exclusions") or "").split(";") if k.strip()]
    exclusions_text = " ".join(stored["exclusions"]).lower()
    found = [k for k in keywords if k in exclusions_text]
    row["exclusions"] = {"expected": keywords, "found": found, "shown": len(stored["exclusions"])}
    if not keywords:
        row["stages"]["exclusions"] = "n/a"
    elif not stored["exclusions"]:
        row["stages"]["exclusions"] = "confirm" if source_type in ("needs_check", "unreadable") else "missing"
    else:
        row["stages"]["exclusions"] = "pass" if len(found) == len(keywords) else "fail"
    if row["stages"]["exclusions"] in ("fail", "missing"):
        row["causes"].append("exclusions_incomplete" if row["stages"]["exclusions"] == "fail" else "exclusions_missing")

    # 6) customer summary
    row["evidence"] = {"status": evidence.get("status"), "label": evidence.get("status_label")}
    row["summary_text"] = (summary_json.get("summary") or "")[:160]
    row["summary_source"] = summary_json.get("source")
    judged = [row["stages"][s] for s in ("fields", "duration", "exclusions") if row["stages"][s] != "n/a"]
    if "fail" in judged:
        row["stages"]["summary"] = "fail"
        row["causes"].append("summary_wrong")
    elif judged and all(o == "pass" for o in judged) and evidence.get("status") in ("confirmed", "confirmed_internal"):
        row["stages"]["summary"] = "pass"
    elif not judged:
        row["stages"]["summary"] = "n/a"
    else:
        row["stages"]["summary"] = "confirm"

    # What SWH read, for review by hand (review.md); no expected values needed.
    def shown_or_suggested(value, key):
        suggestion = (alt.get(f"{key}_suggestion") or {}) if key else {}
        if value:
            return str(value)
        if suggestion.get("status") == "pending" and suggestion.get("value"):
            return f"(blank - suggests {suggestion['value']}, asks the customer to confirm)"
        return "(blank)"

    enrichment = alt.get("openai_invoice_enrichment") or {}
    summary_lines = [line.strip() for line in str(summary_json.get("summary") or "").splitlines() if line.strip()][:3]
    row["review"] = {
        "text": f"{row['text']['engine']} ({row['text']['method'] or 'text'}), {text_chars} characters",
        "brand": shown_or_suggested(stored["brand"], "brand"),
        "model": shown_or_suggested(stored["model"], "model"),
        "serial": shown_or_suggested(stored["serial"], "serial"),
        "invoice_no": shown_or_suggested(invoice_no, None),
        "purchase_date": shown_or_suggested(stored["purchase_date"], None),
        "category": f"{coarse_category or '-'} / {fine_category}",
        "oem_website": page_host or (", ".join(domains[:3]) + " (known site; no page read)" if domains else "(none)"),
        "duration": f"{shown} months" if shown is not None else "(none shown)",
        "warranty_source": source_url or source_type,
        "status": evidence.get("status_label") or "-",
        "summary": " / ".join(summary_lines) or "-",
    }
    row["ai"] = {k: enrichment.get(k) for k in ("provider", "fallback_used", "used") if k in enrichment}
    return row


# --- report ----------------------------------------------------------------------------------------------


def _label(outcome: str) -> str:
    return {"pass": "pass", "confirm": "please confirm", "missing": "missing", "fail": "FAIL", "n/a": "n/a"}[outcome]


def render_report(rows: List[Dict[str, Any]], enabled: Dict[str, Any], title: str) -> Tuple[List[str], Dict[str, Any]]:
    lines = [
        f"## {title}",
        "",
        f"- Invoices: {len(rows)}",
        f"- AI: OpenAI {'on' if enabled['openai'] else 'off'}, Mistral {'on' if enabled['mistral'] else 'off'}, "
        f"vision tier {'on' if enabled['vision'] else 'off'}; network {'blocked (--offline)' if enabled['offline'] else 'on'}",
        "- Outcomes: pass; please confirm (acceptable: the app asks the customer); missing; FAIL (confident wrong); n/a (no expected value).",
        "",
        "### Summary",
        "",
        "| Stage | Judged | Pass | Please confirm | Missing | FAIL | Acceptable rate |",
        "|---|---|---|---|---|---|---|",
    ]
    rates: Dict[str, Any] = {}
    for stage in STAGES:
        counts = Counter(r["stages"].get(stage, "n/a") for r in rows)
        judged = sum(v for k, v in counts.items() if k != "n/a")
        acceptable = counts["pass"] + counts["confirm"]
        rate = f"{acceptable}/{judged} ({acceptable / judged:.0%})" if judged else "-"
        rates[stage] = {"judged": judged, "acceptable": acceptable, **{k: counts[k] for k in ("pass", "confirm", "missing", "fail")}}
        lines.append(f"| {stage} | {judged} | {counts['pass']} | {counts['confirm']} | {counts['missing']} | {counts['fail']} | {rate} |")
    total_seconds = sum(r.get("seconds", 0) for r in rows)
    costs = [r.get("cost_usd") for r in rows]
    cost_text = "not priced (set COST_* prices)" if any(c is None for c in costs) else f"${sum(c or 0 for c in costs):.4f}"
    calls = Counter()
    for r in rows:
        for provider, u in (r.get("usage") or {}).items():
            calls[provider] += u["calls"]
    lines += ["", f"Time: {total_seconds:.1f} s total. API calls: {dict(calls) or 'none'}. Cost: {cost_text}.", "", "### Failures by cause", ""]
    by_cause: Dict[str, List[str]] = defaultdict(list)
    for r in rows:
        for cause in r["causes"]:
            by_cause[cause].append(r["file"])
    if by_cause:
        lines += ["| Cause | Count | Invoices |", "|---|---|---|"]
        for cause, files in sorted(by_cause.items(), key=lambda kv: (-len(kv[1]), kv[0])):
            lines.append(f"| {cause} | {len(files)} | {', '.join(files)} |")
    else:
        lines.append("None.")
    lines += ["", "### Per invoice", ""]
    for r in rows:
        lines += [f"#### {r['file']}", ""]
        if r.get("error"):
            lines += [f"- Error: {r['error']}", ""]
            continue
        f = r["fields"]
        lines += [
            f"- Pipeline job: {r['job']}; time {r['seconds']} s; API {r.get('usage') or 'none'}; cost "
            + ("not priced" if r.get("cost_usd") is None else f"${r['cost_usd']:.4f}"),
            f"- Text read: **{_label(r['stages']['text'])}** - engine {r['text']['engine']} ({r['text']['method'] or 'text'}), {r['text']['chars']} characters",
            f"- Fields: **{_label(r['stages']['fields'])}** - "
            + "; ".join(f"{k} {_label(v)} ({f['values'].get(k)!s})" for k, v in f["outcomes"].items())
            + (f"; suggestions {f['suggestions']}" if f["suggestions"] else ""),
            f"- Brand to OEM domain: **{_label(r['stages']['oem_domain'])}** - company {r['oem']['company']}, domains {r['oem']['domains'] or 'none'}, expected {r['oem']['expected_host'] or '-'}",
            f"- Warranty page: **{_label(r['stages']['warranty_page'])}** - {r['page']['url'] or 'none'} ({r['page']['type']})",
            f"- Duration: **{_label(r['stages']['duration'])}** - shown {r['duration']['shown'] if r['duration']['shown'] is not None else 'none'}"
            f" months, expected {r['duration']['expected'] or '-'}; evidence {r['evidence']['label'] or '-'}",
            f"- Exclusions: **{_label(r['stages']['exclusions'])}** - expected {r['exclusions']['expected'] or '-'}, found {r['exclusions']['found'] or '-'} ({r['exclusions']['shown']} shown)",
            f"- Customer summary: **{_label(r['stages']['summary'])}** - {r['summary_source']}: {r['summary_text']!r}",
            "",
        ]
    return lines, rates


def load_expected(path: Path) -> Dict[str, Dict[str, str]]:
    """Expected values per file; optional - an absent or header-only file means review mode only."""
    if not path.exists():
        return {}
    with path.open(encoding="utf-8-sig", newline="") as fh:
        return {row["file"].strip(): row for row in csv.DictReader(fh) if (row.get("file") or "").strip()}


def ensure_expected_template(path: Path) -> None:
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(",".join(EXPECTED_COLUMNS) + "\n", encoding="utf-8")


# --- review.md: what SWH read, marked by hand ---------------------------------------------------------------

REVIEW_ITEMS = [
    # (key, label, stage the hand mark counts towards)
    ("text", "Text read (engine, characters)", "text"),
    ("brand", "Brand", "fields"),
    ("model", "Model", "fields"),
    ("serial", "Serial", "fields"),
    ("invoice_no", "Invoice number", "fields"),
    ("purchase_date", "Purchase date", "fields"),
    ("category", "Category (coarse / fine)", "fields"),
    ("oem_website", "OEM website used", "oem_domain"),
    ("warranty_source", "Warranty source URL", "warranty_page"),
    ("duration", "Warranty duration found", "duration"),
    ("status", "Estimated / please confirm status", "summary"),
    ("summary", "Customer summary (first lines)", "summary"),
]
_ITEM_BY_LABEL = {label: (key, stage) for key, label, stage in REVIEW_ITEMS}
_PASS_MARKS = {"y", "yes", "ok", "pass", "true", "1", "correct", "✓", "✔"}
_FAIL_MARKS = {"n", "no", "x", "fail", "false", "0", "wrong", "✗", "✘"}
_CONFIRM_MARKS = {"?", "confirm", "please confirm", "asks", "acceptable"}


def _cell(value: Any) -> str:
    return str(value if value is not None else "").replace("\r", " ").replace("\n", " / ").replace("|", "\\|").strip()


def _uncell(value: str) -> str:
    return value.replace("\\|", "|").strip()


def _split_row(line: str) -> List[str]:
    """Cells of a markdown table row, honouring escaped pipes."""
    body = line.strip()
    if body.startswith("|"):
        body = body[1:]
    if body.endswith("|") and not body.endswith("\\|"):
        body = body[:-1]
    cells, current, i = [], "", 0
    while i < len(body):
        if body[i] == "\\" and i + 1 < len(body) and body[i + 1] == "|":
            current += "\\|"
            i += 2
            continue
        if body[i] == "|":
            cells.append(current)
            current = ""
        else:
            current += body[i]
        i += 1
    cells.append(current)
    return [_uncell(c) for c in cells]


def mark_outcome(ok: str, correct_value: str) -> Optional[str]:
    """pass / fail / confirm from a hand mark; None when unmarked."""
    mark = (ok or "").strip().lower()
    if mark in _PASS_MARKS:
        return "pass"
    if mark in _FAIL_MARKS or (not mark and (correct_value or "").strip()):
        return "fail"
    if mark in _CONFIRM_MARKS:
        return "confirm"
    return None


def parse_review_marks(path: Path) -> Dict[Tuple[str, str, str], Dict[str, str]]:
    """Marks from an existing review.md: (file, provider, item key) -> {value, ok, correct}."""
    marks: Dict[Tuple[str, str, str], Dict[str, str]] = {}
    if not path.exists():
        return marks
    file_name, provider = None, None
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("### "):
            title = line[4:].strip()
            file_name, _, provider = title.partition(" | provider ")
            provider = provider.strip() or "auto"
            continue
        if not file_name or not line.startswith("|") or line.startswith("|---") or line.startswith("| Item |"):
            continue
        cells = _split_row(line)
        if len(cells) < 4 or cells[0] not in _ITEM_BY_LABEL:
            continue
        key, _stage = _ITEM_BY_LABEL[cells[0]]
        marks[(file_name.strip(), provider, key)] = {"value": cells[1], "ok": cells[2], "correct": cells[3]}
    return marks


def hand_mark_counts(rows_by_provider: Dict[str, List[Dict[str, Any]]], marks) -> Dict[str, Dict[str, Counter]]:
    """Per provider and stage: pass / fail / confirm / unmarked counts from the marks that still apply."""
    out: Dict[str, Dict[str, Counter]] = {}
    for provider, rows in rows_by_provider.items():
        per_stage: Dict[str, Counter] = defaultdict(Counter)
        for row in rows:
            for key, _label_, stage in REVIEW_ITEMS:
                if key not in (row.get("review") or {}):
                    continue
                mark = marks.get((row["file"], provider, key))
                value = _uncell(_cell(row["review"][key]))
                outcome = mark_outcome(mark["ok"], mark["correct"]) if mark and mark["value"] == value else None
                per_stage[stage][outcome or "unmarked"] += 1
        out[provider] = per_stage
    return out


def write_review(rows_by_provider: Dict[str, List[Dict[str, Any]]], out: Path) -> Dict[str, Dict[str, Counter]]:
    """review.md: SWH's reading of every invoice with blank "OK?" / "Correct value if wrong" columns.
    Marks already in the file are kept when the value SWH read is unchanged; otherwise they are cleared and
    listed under "Marks cleared"."""
    marks = parse_review_marks(out)
    counts = hand_mark_counts(rows_by_provider, marks)
    cleared: List[str] = []
    lines = [
        "# Real-invoice review",
        "",
        "Local only - real_invoices/ is git-ignored. Never commit this file or the invoices.",
        "",
        'Mark each row: "OK?" = y / n / ? (? = SWH asked the customer to confirm, which is acceptable). Put the '
        'right value in "Correct value if wrong" (that alone counts as n). Re-run the runner to turn the marks '
        "into counts; a mark is kept while SWH's value is unchanged.",
        "",
        "## Hand-marked results",
        "",
        "| Provider | Stage | Pass | Please confirm | Fail | Unmarked | Pass rate (marked) |",
        "|---|---|---|---|---|---|---|",
    ]
    for provider, per_stage in counts.items():
        for stage in STAGES:
            c = per_stage.get(stage)
            if not c:
                continue
            marked = c["pass"] + c["fail"] + c["confirm"]
            rate = f"{c['pass'] + c['confirm']}/{marked}" if marked else "-"
            lines.append(f"| {provider} | {stage} | {c['pass']} | {c['confirm']} | {c['fail']} | {c['unmarked']} | {rate} |")
    body: List[str] = []
    for provider, rows in rows_by_provider.items():
        for row in rows:
            body += ["", f"### {row['file']} | provider {provider}", ""]
            if row.get("error"):
                body.append(f"Error: {row['error']}")
            body += ["| Item | SWH read | OK? | Correct value if wrong |", "|---|---|---|---|"]
            for key, label, _stage in REVIEW_ITEMS:
                if key not in (row.get("review") or {}):
                    continue
                value = _cell(row["review"][key])
                mark = marks.get((row["file"], provider, key))
                ok, correct = "", ""
                if mark:
                    if mark["value"] == _uncell(value):
                        ok, correct = mark["ok"], mark["correct"]
                    elif mark["ok"] or mark["correct"]:
                        cleared.append(f"{row['file']} / {provider} / {label}: was \"{mark['value']}\", now \"{_uncell(value)}\"")
                body.append(f"| {label} | {value} | {_cell(ok)} | {_cell(correct)} |")
    if cleared:
        lines += ["", "## Marks cleared (SWH now reads a different value)", ""] + [f"- {c}" for c in cleared]
    lines += ["", "## Invoices"] + body
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return counts


# --- provider comparison --------------------------------------------------------------------------------------


def compare_providers(rows_by_provider: Dict[str, List[Dict[str, Any]]], hand_counts) -> List[str]:
    lines = ["## Provider comparison", "",
             "Each provider ran alone (fallback off) on the same files. Stage counts use expected.csv where filled in; "
             "hand marks come from review.md.", "",
             "| Provider | Fields acceptable | Warranty page acceptable | Duration acceptable | Fields (hand marks) | Time (s) | API calls | Tokens in/out | Cost |",
             "|---|---|---|---|---|---|---|---|---|"]
    for provider, rows in rows_by_provider.items():
        def rate(stage):
            c = Counter(r["stages"].get(stage, "n/a") for r in rows)
            judged = sum(v for k, v in c.items() if k != "n/a")
            return f"{c['pass'] + c['confirm']}/{judged}" if judged else "-"

        hc = (hand_counts.get(provider) or {}).get("fields") or Counter()
        marked = hc["pass"] + hc["fail"] + hc["confirm"]
        calls = sum(u["calls"] for r in rows for u in (r.get("usage") or {}).values())
        tin = sum(u["input_tokens"] for r in rows for u in (r.get("usage") or {}).values())
        tout = sum(u["output_tokens"] for r in rows for u in (r.get("usage") or {}).values())
        costs = [r.get("cost_usd") for r in rows]
        cost = "not priced" if any(c is None for c in costs) else f"${sum(c or 0 for c in costs):.4f}"
        lines.append(
            f"| {provider} | {rate('fields')} | {rate('warranty_page')} | {rate('duration')} | "
            f"{(str(hc['pass'] + hc['confirm']) + '/' + str(marked)) if marked else '-'} | "
            f"{sum(r.get('seconds', 0) for r in rows):.1f} | {calls} | {tin}/{tout} | {cost} |"
        )
    providers = list(rows_by_provider)
    if len(providers) == 2:
        a, b = providers
        by_file = {r["file"]: r for r in rows_by_provider[b]}
        lines += ["", f"### Where {a} and {b} read differently", "", f"| File | Item | {a} | {b} |", "|---|---|---|---|"]
        differences = 0
        for ra in rows_by_provider[a]:
            rb = by_file.get(ra["file"])
            if not rb:
                continue
            for key, label, _stage in REVIEW_ITEMS:
                if key in ("text", "summary"):
                    continue
                va, vb = (ra.get("review") or {}).get(key), (rb.get("review") or {}).get(key)
                if va != vb:
                    differences += 1
                    lines.append(f"| {ra['file']} | {label} | {_cell(va)} | {_cell(vb)} |")
        if not differences:
            lines.append("| - | no differences | - | - |")
    return lines


# --- main -----------------------------------------------------------------------------------------------------


def run_one(folder: Path, files: List[Path], args) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    enabled = configure_environment(offline=args.offline, no_ai=args.no_ai, no_vision=args.no_vision, provider=args.provider)
    sys.path.insert(0, str(ROOT))
    from fastapi.testclient import TestClient

    from app.deps import init_db
    from app.main import app

    init_db()
    _install_usage_hooks()
    client = TestClient(app)
    token = client.post(
        "/auth/login",
        data={"username": os.environ["ADMIN_USER"], "password": os.environ["ADMIN_PASS"]},
        headers={"accept": "application/json"},
    ).json()["access_token"]
    auth = {"Authorization": f"Bearer {token}"}
    expected = load_expected(folder / "expected.csv")
    rows = []
    for path in files:
        rows.append(evaluate(path, expected.get(path.name, {}), client, auth))
        rows[-1]["provider"] = enabled["provider"]
        print(f"[{enabled['provider']}] {path.name}: " + ", ".join(f"{s} {_label(rows[-1]['stages'].get(s, 'n/a'))}" for s in STAGES))
    return rows, enabled


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--dir", default=str(ROOT / "real_invoices"))
    parser.add_argument("--offline", action="store_true", help="block all non-loopback network")
    parser.add_argument("--no-ai", action="store_true", help="do not use AI even if keys are present")
    parser.add_argument("--no-vision", action="store_true", help="never send photos to the AI vision tier")
    parser.add_argument("--provider", choices=("auto", "openai", "mistral", "both"), default="auto",
                        help="AI provider: auto (keys present, normal fallback), openai, mistral, or both (compared)")
    parser.add_argument("--rows-json", help=argparse.SUPPRESS)  # internal: one provider's rows for --provider both
    args = parser.parse_args(argv)
    folder = Path(args.dir).resolve()
    ensure_expected_template(folder / "expected.csv")
    files = sorted(p for p in folder.iterdir() if p.is_file() and p.suffix.lower() in INVOICE_SUFFIXES)
    if not files:
        print(f"No invoices in {folder}. Add files (expected.csv is optional).")
        return 0

    if args.rows_json:  # child process of --provider both
        try:
            rows, enabled = run_one(folder, files, args)
        except ProviderUnavailable as exc:
            print(str(exc))
            return 2
        Path(args.rows_json).write_text(json.dumps({"rows": rows, "enabled": enabled}, default=str), encoding="utf-8")
        return 0

    rows_by_provider: Dict[str, List[Dict[str, Any]]] = {}
    enabled_by_provider: Dict[str, Dict[str, Any]] = {}
    skipped: Dict[str, str] = {}
    if args.provider == "both":
        tmp = Path(tempfile.mkdtemp(prefix="swh_real_invoices_both_"))
        for provider in ("openai", "mistral"):
            out = tmp / f"{provider}.json"
            cmd = [sys.executable, str(Path(__file__).resolve()), "--dir", str(folder), "--provider", provider, "--rows-json", str(out)]
            cmd += [flag for flag, on in (("--offline", args.offline), ("--no-vision", args.no_vision)) if on]
            proc = subprocess.run(cmd, cwd=str(ROOT), capture_output=True, text=True)
            print(proc.stdout, end="")
            if proc.returncode != 0 or not out.exists():
                reason = ([line for line in proc.stdout.splitlines() if line.strip()] or [f"exit {proc.returncode}"])[-1]
                skipped[provider] = reason
                print(f"--provider {provider} did not run: {reason}")
                continue
            data = json.loads(out.read_text(encoding="utf-8"))
            rows_by_provider[provider], enabled_by_provider[provider] = data["rows"], data["enabled"]
        if not rows_by_provider:
            return 2
    else:
        try:
            rows, enabled = run_one(folder, files, args)
        except ProviderUnavailable as exc:
            print(str(exc))
            return 2
        rows_by_provider[enabled["provider"]], enabled_by_provider[enabled["provider"]] = rows, enabled

    hand_counts = write_review(rows_by_provider, folder / "review.md")
    print(f"Review: {folder / 'review.md'}")
    has_expected = bool(load_expected(folder / "expected.csv"))
    if has_expected or args.provider == "both":
        sections: List[str] = ["# Real-invoice run", "", "Local only - real_invoices/ is git-ignored. Never commit this report or the invoices.", ""]
        if args.provider == "both":
            sections += compare_providers(rows_by_provider, hand_counts)
            sections += [f"- {provider} did not run: {reason}" for provider, reason in skipped.items()] + [""]
        for provider, rows in rows_by_provider.items():
            report_lines, rates = render_report(rows, enabled_by_provider[provider], f"Provider: {provider}")
            sections += report_lines
            print(f"[{provider}] acceptable per stage: " + ", ".join(f"{s} {r['acceptable']}/{r['judged']}" for s, r in rates.items()))
        (folder / "report.md").write_text("\n".join(sections) + "\n", encoding="utf-8")
        print(f"Report: {folder / 'report.md'}")
    else:
        print("No expected.csv values: wrote review.md only (mark it by hand and re-run for counts).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
