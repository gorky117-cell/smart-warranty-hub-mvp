"""Regression lock for Samsung- and printer/Epson-specific warranty behaviour (work plan step 2).

Inputs are the parsed outputs of the two curated official OEM pages, captured live on 2026-10-02
(`tests/fixtures/oem_terms_captured_2026-10-02.json`). Network access is mocked out; every
assertion records the output the code produced on that date. These tests must keep passing when
duration selection is reworked (step 8).
"""

import json
from pathlib import Path

import pytest

from app.db import SessionLocal
from app.models import CanonicalWarranty
from app.services import oem_adapters, oem_parsers
from app.services import terms_lookup as tl
from app.services.summary_engine import build_layman_summary
from app.services.warranty_discovery import DiscoverySource
from app.services.warranty_parser import ParsedTerms

_FIXTURE = json.loads(
    (Path(__file__).parent / "fixtures" / "oem_terms_captured_2026-10-02.json").read_text(encoding="utf-8")
)
SAMSUNG_IN = _FIXTURE["samsung"]["url"]
SAMSUNG_US = "https://www.samsung.com/us/support/warranty/"
SAMSUNG_NOTEBOOK = "https://www.samsung.com/in/support/note-warranty/"
EPSON_L3250 = _FIXTURE["epson"]["url"]

SAMSUNG_TERMS = [
    "Standard coverage for 12 months from purchase date.",
    "Limited International One Year Warranty",
    "Warranty does not cover normal wear and tear (including, without limitation, wear and tear of camera lenses, batteries or displays).",
    "The limited warranty period of 1 year will apply, regardless of the warranty period of the country where the product was first sold.",
    "The company's obligation under this warranty shall be limited to repair or providing replacement of part/s only.",
    "The company's obligation under this warranty shall be limited to repairing or providing replacement of part/s, which are found to be defective.",
]
SAMSUNG_EXCLUSIONS = [
    "Warranty does not cover repair due to external factors/medium/data types.",
    "If the product is not used as per its usage specifications(example: Personal, Commercial etc.)",
    "If the product has failed under certain conditions/types(example: Waterlogging, Misuse etc.)",
    "The original serial number is removed, obliterated or altered from the machine or cabinet.",
    "Defects due to cause beyond control like lightning, abnormal voltage, acts of God or while in transit to service Center or purchaser's residence.",
]
SAMSUNG_CLAIM_STEPS = [
    "Out of Warranty Repair Charges",
    "Digital Service Center",
    "Service Center",
    "Type of Service (Handset) - Repair service carried at Samsung authorized service center.",
    "Exchange warranty applicable at Samsung authorized service center. Warranty applicable from customer purchase date",
]
EPSON_CLAIM_STEPS = [
    "Product Registration",
    "Warranty Check",
    "Check Repair Status",
    "Service Center Locator",
    "FOR SERVICE SUPPORT, CALL",
]
DEFAULT_CLAIM_STEPS = [
    "Keep your invoice or receipt ready.",
    "Share model/serial details with support.",
    "Provide photos or logs to speed up verification.",
]


def _parsed(name: str, **overrides) -> ParsedTerms:
    data = dict(_FIXTURE[name]["parsed"])
    data.update(overrides)
    data["raw_text"] = None
    return ParsedTerms(**data)


def _lookup(monkeypatch, sources, pages, **kwargs):
    monkeypatch.setattr(
        tl,
        "discover_sources",
        lambda **_kw: [DiscoverySource(url=u, source_type="oem_warranty", score=10, official=True) for u in sources],
    )
    monkeypatch.setattr(
        tl,
        "parse_terms_from_url",
        lambda url, *_a, **_kw: (pages[url], None) if url in pages else (None, "not mocked"),
    )
    with SessionLocal() as db:
        return tl.lookup_terms(db, force_refresh=True, **kwargs)


def test_fixture_records_raw_samsung_page_duration_as_60_months():
    # The live Samsung India page parses to 60 months (an appliance/extended figure). The
    # Samsung mobile normalisation below is what turns this into the correct 12 months.
    assert _FIXTURE["samsung"]["parsed"]["duration_months"] == 60
    assert _FIXTURE["epson"]["parsed"]["duration_months"] == 12


def test_samsung_mobile_india_terms_locked(monkeypatch):
    result = _lookup(
        monkeypatch,
        [SAMSUNG_IN],
        {SAMSUNG_IN: _parsed("samsung")},
        brand="Samsung",
        category="mobile",
        region="IN",
        model_code="SM-M175E",
        product_name="Samsung Galaxy M17e 5G Mobile",
    )

    assert result.duration_months == 12
    assert result.terms == SAMSUNG_TERMS
    assert result.exclusions == SAMSUNG_EXCLUSIONS
    assert result.claim_steps == SAMSUNG_CLAIM_STEPS
    assert "Additional Support" not in result.claim_steps
    assert result.source_url == SAMSUNG_IN
    assert result.source_urls == [SAMSUNG_IN]
    assert tl.classify_terms_source_url(result.source_url, "Samsung") == "approved_oem_source"
    joined = " ".join(result.terms).lower()
    for blocked in ("60 months", "5 years", "24 months", "2 years", "coverplus", "extended warranty"):
        assert blocked not in joined


def test_samsung_wrong_region_source_is_skipped(monkeypatch):
    result = _lookup(
        monkeypatch,
        [SAMSUNG_US, SAMSUNG_IN],
        {SAMSUNG_US: _parsed("samsung", duration_months=24), SAMSUNG_IN: _parsed("samsung")},
        brand="Samsung",
        category="mobile",
        region="IN",
    )

    assert result.duration_months == 12
    assert result.source_urls == [SAMSUNG_IN]
    assert tl._source_region_conflicts(SAMSUNG_US, "IN") is True
    assert tl._source_region_conflicts(SAMSUNG_IN, "IN") is False


def test_samsung_notebook_page_rejected_for_mobile_in_auto_discovery(monkeypatch):
    notebook = _parsed("samsung", terms=["Notebook PC warranty 24 months"])
    result = _lookup(
        monkeypatch,
        [SAMSUNG_NOTEBOOK],
        {SAMSUNG_NOTEBOOK: notebook},
        brand="Samsung",
        category="mobile",
        region="IN",
    )

    assert result.duration_months == 12
    assert result.source_url == "internal://default_rules"
    assert tl.classify_terms_source_url(result.source_url, "Samsung") == "default_rules"
    assert result.claim_steps == DEFAULT_CLAIM_STEPS


def test_samsung_notebook_manual_url_rejected_for_mobile(monkeypatch):
    notebook = _parsed("samsung", terms=["Notebook PC warranty 24 months"])
    result = _lookup(
        monkeypatch,
        [],
        {SAMSUNG_NOTEBOOK: notebook},
        brand="Samsung",
        category="mobile",
        region="IN",
        url_override=SAMSUNG_NOTEBOOK,
    )

    assert result.duration_months == 12
    assert result.source_url == "internal://manual_url_product_context_conflict"
    assert result.source_urls == []
    assert tl.classify_terms_source_url(result.source_url, "Samsung") == "internal"


def test_samsung_mobile_normalisation_fills_claim_steps_when_page_has_none():
    result = tl.TermsResult(
        duration_months=60,
        terms=["Limited International One Year Warranty", "Samsung Care+ extended warranty for 2 years"],
        exclusions=[],
        claim_steps=["News", "Alerts", "Community"],
        source_url=SAMSUNG_IN,
        source_urls=[SAMSUNG_IN],
        raw_text=None,
    )

    out = tl._normalize_result_for_context(result, brand="Samsung", norm_category="mobile", source_url=SAMSUNG_IN)

    # Fix run B7: the 12-month force was removed; duration is chosen from evidence at merge time
    # (the end-to-end locks above still give 12). Term and claim-step filtering are unchanged.
    assert out.duration_months == 60
    assert out.terms == ["Limited International One Year Warranty"]
    assert out.claim_steps == [
        "Use Samsung warranty check or product registration.",
        "Check repair status or locate a Samsung service center.",
        "Keep invoice, model and serial details ready for support.",
    ]


def test_samsung_normalisation_does_not_touch_other_brands_or_categories():
    def fresh():
        return tl.TermsResult(
            duration_months=60,
            terms=["Limited International One Year Warranty"],
            exclusions=[],
            claim_steps=[],
            source_url=SAMSUNG_IN,
            source_urls=[SAMSUNG_IN],
            raw_text=None,
        )

    assert tl._normalize_result_for_context(fresh(), brand="LG", norm_category="mobile", source_url=SAMSUNG_IN).duration_months == 60
    assert tl._normalize_result_for_context(fresh(), brand="Samsung", norm_category="appliance", source_url=SAMSUNG_IN).duration_months == 60
    assert (
        tl._normalize_result_for_context(fresh(), brand="Samsung", norm_category="mobile", source_url="https://example.com/w").duration_months
        == 60
    )


def test_epson_l3250_printer_india_terms_locked(monkeypatch):
    result = _lookup(
        monkeypatch,
        [EPSON_L3250],
        {EPSON_L3250: _parsed("epson")},
        brand="Epson",
        category="electronics",
        region="IN",
        model_code="L3250",
        product_name="Epson L 3250 Printer",
    )

    assert result.duration_months == 12
    assert len(result.terms) == 3
    assert result.terms[0] == "Standard coverage for 12 months from purchase date."
    assert "30,000 prints, whichever comes first" in result.terms[1]
    assert "coverage of printhead" in result.terms[2]
    assert result.exclusions == []
    assert result.claim_steps == EPSON_CLAIM_STEPS
    assert result.source_url == EPSON_L3250
    assert result.source_urls == [EPSON_L3250]
    assert tl.classify_terms_source_url(result.source_url, "Epson") == "approved_oem_source"
    assert "coverplus" not in " ".join(result.terms).lower()


def test_epson_coverplus_page_text_never_sets_base_duration(monkeypatch):
    with_plan = _parsed(
        "epson",
        terms=_FIXTURE["epson"]["parsed"]["terms"]
        + ["Epson CoverPlus extends the standard warranty on our products for up to 5 years."],
    )
    result = _lookup(
        monkeypatch,
        [EPSON_L3250],
        {EPSON_L3250: with_plan},
        brand="Epson",
        category="electronics",
        region="IN",
        model_code="L3250",
    )

    assert result.duration_months == 12
    assert "coverplus" not in " ".join(result.terms).lower()


def test_samsung_and_printer_summary_wording_locked():
    samsung = CanonicalWarranty(
        id="wty_lock_samsung",
        brand="Samsung",
        model_code="M17E",
        coverage_months=12,
        terms=SAMSUNG_TERMS,
        exclusions=SAMSUNG_EXCLUSIONS,
        claim_steps=SAMSUNG_CLAIM_STEPS,
        alternatives={"terms_source_type": "approved_oem_source", "terms_source_url": SAMSUNG_IN},
    )
    joined = " ".join(sum((build_layman_summary(samsung)[k] for k in ("pros", "cons", "claim_friction")), [])).lower()
    assert "standard warranty coverage shown: 12 months" in joined
    assert "60 months" not in joined

    epson = CanonicalWarranty(
        id="wty_lock_epson",
        brand="Epson",
        model_code="L3250",
        coverage_months=12,
        terms=["Standard coverage for 12 months from purchase date.", "Warranty includes coverage of printhead for high volume printing."],
        claim_steps=EPSON_CLAIM_STEPS,
        alternatives={"terms_source_type": "approved_oem_source", "terms_source_url": EPSON_L3250},
    )
    pros = " ".join(build_layman_summary(epson)["pros"]).lower()
    assert "12 months" in pros
    assert "printhead" in pros


def test_samsung_adapter_and_parser_cues_locked():
    adapter = oem_adapters.get_adapter("Samsung")
    assert adapter is not None
    assert adapter.approved_domains == ("samsung.com", "samsungmobile.com")
    assert oem_adapters.get_adapter("Epson") is None

    # Note: "warranty: 10 years" (space after the colon) does not match today; logged in MEMORY 90.
    parsed = oem_parsers.parse_oem_text("Compressor warranty 10 years", brand_hint="Samsung")
    assert parsed["extended_parts"] == {"Compressor": "10 years"}


@pytest.mark.parametrize(
    "category,expected",
    [("mobile", "mobile"), ("Mobile Phone", "mobile"), ("electronics", "electronics"), ("printer", "general")],
)
def test_terms_category_normalisation_locked(category, expected):
    assert tl._normalize_category(category) == expected
