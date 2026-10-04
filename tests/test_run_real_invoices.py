"""The real-invoice runner works end to end on synthetic invoices (consolidated run P3.11).

Runs as a subprocess (the runner configures its own throwaway database before importing the app),
offline and without AI, so it never touches the network, API keys or the repo's data files."""

import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

EXPECTED = """file,brand,model,serial,invoice_no,purchase_date,category,warranty_months,key_exclusions,oem_url
samsung_text.pdf,Samsung,SM-S928BZKGINS,R5CX40VP8LA,INV-2026-00145,2026-01-22,mobile,12,accidental;liquid,https://www.samsung.com/in/support/warranty/
flipkart_philips.txt,Philips,,,FAABCD2600012345,2026-01-05,kitchen_appliance,,,
reliance_reconnect.txt,Reconnect,RAC-SPL15,,RD-4455667,2026-03-22,,12,,
"""


def test_runner_writes_a_report_for_three_synthetic_invoices(tmp_path):
    shutil.copy(ROOT / "test_data" / "invoice_full_details.pdf", tmp_path / "samsung_text.pdf")
    shutil.copy(ROOT / "tests" / "fixtures" / "marketplace" / "flipkart.txt", tmp_path / "flipkart_philips.txt")
    shutil.copy(ROOT / "tests" / "fixtures" / "marketplace" / "reliance_digital.txt", tmp_path / "reliance_reconnect.txt")
    (tmp_path / "expected.csv").write_text(EXPECTED, encoding="utf-8")
    before = subprocess.run(["git", "status", "--porcelain"], cwd=ROOT, capture_output=True, text=True).stdout

    proc = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "run_real_invoices.py"), "--dir", str(tmp_path), "--offline", "--no-ai"],
        cwd=ROOT, capture_output=True, text=True, timeout=600,
    )
    assert proc.returncode == 0, proc.stderr[-2000:]
    report = (tmp_path / "report.md").read_text(encoding="utf-8")
    assert "| text | 3 | 3 |" in report
    assert "network blocked (--offline)" in report and "OpenAI off" in report
    samsung = report.split("### samsung_text.pdf")[1]
    assert "Fields: **pass**" in samsung and "Brand to OEM domain: **pass**" in samsung
    reliance = report.split("### reliance_reconnect.txt")[1].split("###")[0]
    # Unknown brand: offered for confirmation, and no guessed warranty period.
    assert "brand please confirm" in reliance and "Duration: **please confirm** - shown none months" in reliance
    assert subprocess.run(["git", "status", "--porcelain"], cwd=ROOT, capture_output=True, text=True).stdout == before
