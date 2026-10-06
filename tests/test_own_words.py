"""Step 2 of the own-words run: terms become structured facts in SWH's words; no brand sentence reaches customers
unless the brand allows it (reuse policy full_text_ok)."""

import json
import re
from datetime import date, datetime

import pytest

from app.models import CanonicalWarranty
from app.services import customer_content as cc
from app.services import reuse_policy, warranty_facts
from app.services.summary_engine import build_layman_summary
from app.services.warranty_card import five_lines

SRC = "https://www.example-brand.com/in/support/warranty/"
# Brand-style wording for a mix of product types (written for this test, in the style of real terms pages).
CASES = {
    "phone": ("Samsung", "Galaxy M17e", "SM-M175F", 12,
              ["Samsung warrants that the product shall be free from defects in material and workmanship under normal use.",
               "Warranty does not cover normal wear and tear of batteries, camera lenses or displays."],
              ["Defects caused by liquid ingress, lightning or abnormal voltage are excluded from the warranty.",
               "Products with tampered or removed serial number labels shall not be covered."],
              ["Visit the nearest Samsung authorized service center along with the original invoice.",
               "Customers may also call the toll-free number for doorstep support in select cities."]),
    "fridge": ("LG", "LG Double Door Refrigerator", "GL-T292RPZY", 12,
               ["LG will repair or replace free of charge any part found defective due to manufacturing defects.",
                "The compressor is covered for a period of ten years from the date of purchase."],
               ["Damage resulting from voltage fluctuations, fire, floods or acts of God is not covered.",
                "Use of the refrigerator for commercial purposes voids this warranty."],
               ["Register a complaint on the LG website or call the customer care number."]),
    "AC": ("Voltas", "Voltas Split AC", "183V", 12,
           ["The warranty period commences from the date of installation and not from the date of invoice.",
            "Five years warranty on the compressor, subject to installation by authorized personnel."],
           ["Damage due to improper installation or relocation by unauthorized persons is not covered."],
           ["Service is provided at the customer's premises by authorized technicians."]),
    "washing machine": ("IFB", "IFB Front Load Washing Machine", "Senator WXS", 24,
                        ["The motor carries a warranty of four years.",
                         "Product registration within 15 days is mandatory to avail the warranty benefits."],
                        ["Damage caused by rodents, insects or pests and cosmetic damage is excluded."],
                        ["Raise a service request through the IFB app or call the helpline."]),
    "laptop": ("HP", "HP Laptop 15s", "15s-fq5111TU", 12,
               ["HP hardware is warranted against defects in materials and workmanship for the warranty period."],
               ["Software, viruses and loss of data are not covered by the HP limited warranty.",
                "Accidental damage such as drops and spills is not covered unless an accidental damage plan was purchased."],
               ["Carry-in warranty: take the unit to an HP authorized service provider with proof of purchase."]),
    "printer": ("Epson", "EcoTank L3250 Printer", "L3250", 12,
                ["Epson shall repair or replace defective parts free of cost during the warranty period."],
                ["Use of non-genuine ink or consumables, and damage in transit, are not covered."],
                ["Contact the Epson call centre to register a complaint."]),
    "geyser": ("Racold", "Racold Eterno Pro Geyser", "ETERNO PRO 25", 24,
               ["The inner tank carries a warranty of seven years; heating element and thermostat two years."],
               ["Damage due to hard water scaling and electrical supply problems is not covered."],
               ["Installation and service by Racold authorized service partners only."]),
    "TV": ("Sony", "Bravia TV", "KD-55X74L", 12,
           ["The display panel is covered for a period of two years from the date of purchase."],
           ["Physical damage to the panel, including cracks, is not covered under warranty."],
           ["Contact Sony customer care; on-site service is provided for televisions."]),
    "small appliance": ("Bajaj Electricals", "Bajaj Mixer Grinder", "GX 3701", 24,
                        ["Two years warranty on the product and five years on the motor."],
                        ["Jars, blades and gaskets are consumable parts and not covered."],
                        ["Take the product to the nearest Bajaj service centre with the bill."]),
}


def _warranty(case, **kw):
    brand, name, model, months, terms, exclusions, claims = CASES[case]
    base = dict(id=f"wty_ow_{case.replace(' ', '_')}", brand=brand, product_name=name, model_code=model,
                purchase_date=datetime(2026, 1, 10), coverage_months=months, terms=terms, exclusions=exclusions,
                claim_steps=claims, confidence={}, source_artifact_ids=[],
                alternatives={"terms_source_url": SRC, "terms_source_type": "approved_oem_source",
                              "terms_last_refreshed_at": "2026-10-01T09:00:00"})
    base.update(kw)
    return CanonicalWarranty(**base)


def _shingles(text, n=8):
    words = re.findall(r"[a-z0-9]+", text.lower())
    return {" ".join(words[i:i + n]) for i in range(len(words) - n + 1)}


@pytest.mark.parametrize("case", list(CASES))
def test_no_brand_sentence_reaches_customers(case):
    raw = " ".join(CASES[case][4] + CASES[case][5] + CASES[case][6])
    w = cc.tidy(_warranty(case))
    layman = build_layman_summary(w)
    card = five_lines(w, {"status": "confirmed"}, None, today=date(2026, 10, 6))
    shown = " ".join(w.terms + w.exclusions + w.claim_steps
                     + [str(v) for k, v in layman.items() if k != "evidence_status"]
                     + [line["text"] for line in card["lines"]] + [x["text"] for x in card["extras"]]
                     + [cc.export_text(w, {})])
    copied = _shingles(raw) & _shingles(shown)
    assert copied == set(), copied


@pytest.mark.parametrize("case,expected", [
    ("phone", {"period": "Covered for 1 year from the purchase date",
               "exclusions": {"liquid", "power", "serial", "wear"}, "route": {"service_centre", "customer_care", "invoice_needed"}}),
    ("fridge", {"parts": ["Compressor covered for 10 years"], "exclusions": {"power", "natural", "commercial"},
                "covers": {"defects", "free"}, "route": {"customer_care", "online"}}),
    ("AC", {"period": "Covered for 1 year from the installation date", "parts": ["Compressor covered for 5 years"],
            "exclusions": {"installation", "unauthorized_repair", "transit"}, "service_mode": "on_site"}),
    ("washing machine", {"parts": ["Motor covered for 4 years"], "registration_days": 15, "exclusions": {"pests", "cosmetic"}}),
    ("laptop", {"service_mode": "carry_in", "exclusions": {"software", "physical", "liquid"}, "route": {"service_centre", "invoice_needed"}}),
    ("printer", {"covers": {"defects", "free"}, "exclusions": {"consumables", "transit"}}),
    ("geyser", {"parts": ["Inner tank covered for 7 years"], "exclusions": {"power"}}),
    ("TV", {"parts": ["Display panel covered for 2 years"], "exclusions": {"physical"}, "service_mode": "on_site"}),
    ("small appliance", {"parts": ["Motor covered for 5 years"], "exclusions": {"consumables"}}),
])
def test_facts_for_a_mix_of_products(case, expected):
    facts = cc.tidy(_warranty(case)).alternatives["facts"]
    if "period" in expected:
        assert facts["period"]["text"] == expected["period"]
    if "parts" in expected:
        assert [p["text"] for p in facts["part_periods"]][:1] == expected["parts"]
    if "exclusions" in expected:
        assert expected["exclusions"] <= {f["key"] for f in facts["exclusions"]}
    if "covers" in expected:
        assert expected["covers"] <= {f["key"] for f in facts["covers"]}
    if "route" in expected:
        assert expected["route"] <= {f["key"] for f in facts["claim_route"]}
    if "service_mode" in expected:
        assert facts["service_mode"] == expected["service_mode"]
    if "registration_days" in expected:
        assert facts["registration_needed"] and facts["registration_days"] == expected["registration_days"]
    for group in ("covers", "exclusions", "claim_route", "part_periods"):
        for fact in facts[group]:  # every fact keeps its source and the date it was checked
            assert fact["source_url"] == SRC and fact["checked_on"] == "2026-10-01"


def test_authorized_only_when_the_brand_says_so():
    route = warranty_facts.build(brand="Xiaomi", coverage_months=12, terms=[], exclusions=[],
                                 claim_steps=["Bring the phone to the nearest service centre."])["claim_route"]
    assert route[0]["text"] == "Repairs are done at Xiaomi's service centres"


def test_extended_plan_on_the_invoice_is_kept_separate():
    facts = warranty_facts.build(brand="HP", coverage_months=12, terms=[], exclusions=[], claim_steps=[],
                                 invoice_text="1 HP Laptop 15s\n2 HP Care Pack Extended Warranty 2 Years 3,499.00")
    assert facts["period"]["months"] == 12 and len(facts["extended_plans"]) == 1
    assert "separately from the brand's warranty" in facts["extended_plans"][0]["text"]


def test_brand_with_full_text_permission_keeps_its_wording(monkeypatch, tmp_path):
    path = tmp_path / "policy.json"
    path.write_text(json.dumps({"default": "link_only", "brands": {
        "LG": {"policy": "full_text_ok", "granted_by": "LG India legal (test)", "granted_on": "2026-10-06"}}}), encoding="utf-8")
    monkeypatch.setattr(reuse_policy, "_PATH", path)
    reuse_policy.reset_cache()
    try:
        w = cc.tidy(_warranty("fridge"))
        assert w.terms == CASES["fridge"][4] and w.alternatives["facts"]["part_periods"]
        assert cc.tidy(_warranty("phone")).terms[0].startswith("Covered for")  # Samsung: no permission
    finally:
        reuse_policy.reset_cache()


def test_raw_text_is_admin_only(monkeypatch):
    from fastapi.testclient import TestClient

    from app.main import app

    monkeypatch.setenv("RATE_LIMIT_ENABLED", "0")
    client = TestClient(app)
    assert client.get("/admin/warranties/wty_x/oem-text").status_code == 401
