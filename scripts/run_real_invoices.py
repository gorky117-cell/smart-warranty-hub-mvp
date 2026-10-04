"""Send every invoice in real_invoices/ through the full upload pipeline and write real_invoices/report.md.

Real invoices, expected values and the report stay in real_invoices/, which is git-ignored: never commit them.

    python scripts/run_real_invoices.py [--dir real_invoices] [--offline] [--no-ai] [--no-vision]

- Runs the real app in-process (POST /artifacts/upload, as a browser upload does) against a throwaway SQLite
  database, so nothing is written to the app's own database or data/ files.
- AI is on only when keys are present in the local .env (or the environment): OPENAI_API_KEY turns on
  OpenAI invoice enrichment, summaries and the vision tier for unreadable photos; MISTRAL_API_KEY is used
  for summaries when there is no OpenAI key. Key values are never printed or written to the report.
- --offline blocks all non-loopback network (no OEM website lookups); used by the tests.
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
import secrets
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


def configure_environment(*, offline: bool, no_ai: bool, no_vision: bool) -> Dict[str, Any]:
    """Isolated DB, AI only when keys exist, generated admin login. Returns what was enabled (no values)."""
    for key, value in _read_env_file(ROOT / ".env").items():
        os.environ.setdefault(key, value)
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
    has_openai = bool(os.getenv("OPENAI_API_KEY")) and not no_ai
    has_mistral = bool(os.getenv("MISTRAL_API_KEY")) and not no_ai
    os.environ["OPENAI_ENABLED"] = "1" if has_openai else "0"
    os.environ["OPENAI_INVOICE_ENRICHMENT"] = "1" if has_openai else "0"
    os.environ["VISION_AI_EXTRACTION"] = "1" if has_openai and not no_vision else "0"
    os.environ["LLM_PROVIDER"] = "openai" if has_openai else ("mistral" if has_mistral else "none")
    if not has_openai:
        os.environ.pop("OPENAI_API_KEY", None)
    if not has_mistral:
        os.environ.pop("MISTRAL_API_KEY", None)
    if offline:
        _block_network()
    return {"openai": has_openai, "mistral": has_mistral, "vision": has_openai and not no_vision, "offline": offline}


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
        response = real_post(url, *args, **kwargs)
        if "mistral.ai" in str(url):
            USAGE.calls["mistral"] += 1
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
    return row


# --- report ----------------------------------------------------------------------------------------------


def _label(outcome: str) -> str:
    return {"pass": "pass", "confirm": "please confirm", "missing": "missing", "fail": "FAIL", "n/a": "n/a"}[outcome]


def write_report(rows: List[Dict[str, Any]], enabled: Dict[str, Any], out: Path) -> Dict[str, Any]:
    lines = [
        "# Real-invoice run",
        "",
        "Local only - real_invoices/ is git-ignored. Never commit this report or the invoices.",
        "",
        f"- Invoices: {len(rows)}",
        f"- AI: OpenAI {'on' if enabled['openai'] else 'off'}, Mistral {'on' if enabled['mistral'] else 'off'}, "
        f"vision tier {'on' if enabled['vision'] else 'off'}; network {'blocked (--offline)' if enabled['offline'] else 'on'}",
        "- Outcomes: pass; please confirm (acceptable: the app asks the customer); missing; FAIL (confident wrong); n/a (no expected value).",
        "",
        "## Summary",
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
    lines += ["", f"Time: {total_seconds:.1f} s total. API calls: {dict(calls) or 'none'}. Cost: {cost_text}.", "", "## Failures by cause", ""]
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
    lines += ["", "## Per invoice", ""]
    for r in rows:
        lines += [f"### {r['file']}", ""]
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
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return rates


def load_expected(path: Path) -> Dict[str, Dict[str, str]]:
    if not path.exists():
        return {}
    with path.open(encoding="utf-8-sig", newline="") as fh:
        return {row["file"].strip(): row for row in csv.DictReader(fh) if (row.get("file") or "").strip()}


def ensure_expected_template(path: Path) -> None:
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(",".join(EXPECTED_COLUMNS) + "\n", encoding="utf-8")


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--dir", default=str(ROOT / "real_invoices"))
    parser.add_argument("--offline", action="store_true", help="block all non-loopback network")
    parser.add_argument("--no-ai", action="store_true", help="do not use AI even if keys are present")
    parser.add_argument("--no-vision", action="store_true", help="never send photos to the AI vision tier")
    args = parser.parse_args(argv)
    folder = Path(args.dir).resolve()
    ensure_expected_template(folder / "expected.csv")
    files = sorted(p for p in folder.iterdir() if p.is_file() and p.suffix.lower() in INVOICE_SUFFIXES)
    if not files:
        print(f"No invoices in {folder}. Add files and fill expected.csv.")
        return 0

    enabled = configure_environment(offline=args.offline, no_ai=args.no_ai, no_vision=args.no_vision)
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
        print(f"{path.name}: " + ", ".join(f"{s} {_label(rows[-1]['stages'].get(s, 'n/a'))}" for s in STAGES))
    rates = write_report(rows, enabled, folder / "report.md")
    print(f"Report: {folder / 'report.md'}")
    print("Acceptable per stage: " + ", ".join(f"{s} {r['acceptable']}/{r['judged']}" for s, r in rates.items()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
