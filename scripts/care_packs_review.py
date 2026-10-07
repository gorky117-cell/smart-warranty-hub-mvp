"""Write docs/CARE_PACKS_REVIEW.md from data/care_packs/*.json: per product type, the questions and care tips in
tables with an Approve column for the reviewer.

    python scripts/care_packs_review.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def _cell(text) -> str:
    return str(text).replace("|", "/").replace("\n", " ")


def _trigger(trigger: dict, labels: dict) -> str:
    if trigger.get("always"):
        return "always"
    parts = []
    for qid, values in (trigger.get("answers") or {}).items():
        parts.append(f"{qid} = " + " or ".join(labels.get((qid, v), v) for v in values))
    if trigger.get("months_owned_at_least") is not None:
        parts.append(f"owned {trigger['months_owned_at_least']}+ months")
    return "; ".join(parts) or "-"


def build() -> str:
    from app.services import care_packs

    care_packs.reset_cache()
    out = ["# Care packs review worksheet", "",
           "Generated from `data/care_packs/*.json` by `python scripts/care_packs_review.py`. Every pack is a **draft**",
           "until approved on /ui/admin/care-packs (customers see only approved packs). Mark each row in the Approve",
           "column (yes / change: ...), then approve the pack on the admin screen.", "",
           "| Product type | Questions | Tips | Rule problems |", "|---|---|---|---|"]
    packs = [care_packs.file_pack(t) for t in care_packs.product_types()]
    for pack in packs:
        problems = care_packs.validate(pack)
        out.append(f"| {_cell(pack['label'])} | {len(pack['questions'])} | {len(pack['care_tips'])} | "
                   f"{'none' if not problems else _cell('; '.join(problems))} |")
    for pack in packs:
        labels = {(q["id"], a["value"]): a["label"] for q in pack["questions"] for a in q["answers"]}
        out += ["", f"## {pack['label']}", "",
                f"Hazards: {', '.join(pack['hazards']) or 'none'}. Matches: {', '.join(pack['match'].get('keywords') or [])}.", "",
                "### Questions (asked 3 at a time; every question has Skip)", "",
                "| # | Question | Answers | Why we ask | Approve |", "|---|---|---|---|---|"]
        for i, q in enumerate(pack["questions"], 1):
            out.append(f"| {i} | {_cell(q['text'])} | {_cell(' / '.join(a['label'] for a in q['answers']))} | {_cell(q['why'])} | |")
        out += ["", "### Care tips (safety first, then by priority)", "",
                "| # | Tip | Priority | Shown when | Why | Approve |", "|---|---|---|---|---|---|"]
        for i, t in enumerate(pack["care_tips"], 1):
            safety = "Safety: " if t.get("safety") else ""
            out.append(f"| {i} | {safety}{_cell(t['text'])} | {t['priority']} | {_cell(_trigger(t['trigger'], labels))} | "
                       f"{_cell(t['why'])} | |")
        out += ["", "### Maintenance reminders", "", "| Reminder | Interval | Note | Approve |", "|---|---|---|---|"]
        for r in pack["reminders"]:
            out.append(f"| {_cell(r['text'])} | {_cell(r['interval_text'])} | {_cell(r['note'])} | |")
        out += ["", "### Risk factors", "", "| Answer | Effect | Reason | Approve |", "|---|---|---|---|"]
        for r in pack["risk_factors"]:
            answers = " or ".join(labels.get((r["question"], v), v) for v in r["answers"])
            out.append(f"| {_cell(r['question'])} = {_cell(answers)} | {r['effect']} | {_cell(r['reason'])} | |")
        out += ["", "### Usual warranty structure (no numbers)", ""]
        out += [f"- **{_cell(p['part'])}:** {_cell(p['note'])}" for p in pack["warranty_structure"]]
        out += ["", "### Exclusions to look for", ""] + [f"- {_cell(x)}" for x in pack["exclusions_to_look_for"]]
    return "\n".join(out) + "\n"


def main() -> int:
    path = ROOT / "docs" / "CARE_PACKS_REVIEW.md"
    path.write_text(build(), encoding="utf-8")
    print(f"wrote {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
