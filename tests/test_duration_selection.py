"""Product-scoped warranty duration selection (work plan step 8).

The multi-product page below is synthetic, modelled on the structure of an OEM support page that lists
every product family (phones, watches, TVs, accessories, appliance parts) on one page.
"""

from app.models import TermsResult
from app.services import terms_lookup as tl
from app.services.duration_selection import DurationContext, select_duration
from app.services.warranty_parser import duration_candidates, parse_terms_from_text

MULTI_PRODUCT_PAGE = "\n".join(
    [
        "Mobile phones and tablets are covered by our standard warranty.",
        "The limited warranty period of 1 year will apply to the handset.",
        "Smart Watches - 12 months",
        "Wireless Buds - 6 months",
        "Accessories (remote etc.) - 36 months warranty",
        "60 months (only part warranty)",
        "120 months (only part warranty)",
        "Free installation / demo within 6 months from purchase date.",
        "Get 3 year warranty (1 year standard + 2 year additional warranty on selected TV models).",
        "CarePlus extended warranty plan available for up to 2 years.",
    ]
)
PAGE_URL = "https://oem.example/in/support/warranty/"
PHONE = DurationContext(category="mobile", model_code="SM-X100", product_name="Example X100 5G Mobile", region="IN")


def _page_result(text=MULTI_PRODUCT_PAGE, url=PAGE_URL):
    return tl._to_terms_result(parse_terms_from_text(text), url)


def test_legacy_parser_still_takes_page_maximum():
    # Unchanged parser behaviour, recorded for contrast: the maximum over "general" sentences. Here it
    # is the accessories row (36), because `_sentences()` strips the leading "60"/"120" of the part rows.
    assert parse_terms_from_text(MULTI_PRODUCT_PAGE).duration_months == 36


def test_candidates_read_three_digit_months_and_number_words():
    months = {c["months"] for c in duration_candidates("120 months (only part warranty). One year warranty.")}
    assert months == {120, 12}


def test_phone_gets_base_handset_warranty_not_page_maximum():
    choice = select_duration([_page_result()], PHONE)
    assert choice.months == 12
    assert "handset" in choice.evidence and PAGE_URL in choice.evidence


def test_extended_and_additional_plans_are_separated():
    choice = select_duration([_page_result()], PHONE)
    assert any("CarePlus" in plan for plan in choice.optional_plans)
    assert any("additional warranty" in plan for plan in choice.optional_plans)


def test_other_product_family_rows_do_not_set_phone_duration():
    page = "\n".join(["Smart Watches - 24 months", "Accessories - 36 months warranty", "Mobile phone support page."])
    assert select_duration([_page_result(page)], PHONE).months is None


def test_component_and_installation_periods_are_not_base_warranty():
    page = "Phone parts.\n60 months (only part warranty)\nFree installation within 6 months from purchase date."
    assert select_duration([_page_result(page)], PHONE).months is None


def test_sentence_naming_the_model_wins_over_generic_sentence():
    page = "Standard warranty of 2 years on all products.\nThe SM-X100 mobile carries a warranty of 1 year."
    choice = select_duration([_page_result(page)], PHONE)
    assert choice.months == 12


def test_other_country_statement_is_skipped_for_india():
    page = "In the United Kingdom the phone warranty is 24 months.\nIn India the phone warranty is 12 months."
    assert select_duration([_page_result(page)], PHONE).months == 12


def test_source_without_product_context_is_ignored():
    unrelated = _page_result("Refrigerator warranty is 10 years on the compressor and 2 years overall.", "https://oem.example/fridge")
    phone = _page_result("This mobile phone has a warranty of 1 year.", "https://oem.example/phone")
    assert select_duration([unrelated, phone], PHONE).months == 12


def test_merge_never_picks_the_larger_value_just_because_it_is_larger():
    first = TermsResult(duration_months=12, terms=["This mobile phone has a warranty of 1 year."], source_url="https://a.example")
    second = TermsResult(duration_months=24, terms=["Warranty on this mobile phone: 24 months from the date of purchase."], source_url="https://b.example")
    # Equal evidence: the higher-ranked source wins, so the smaller value is kept.
    assert tl._merge_terms_results([first, second], PHONE).duration_months == 12
    # Stronger evidence (names the model) wins regardless of rank or size.
    second.terms = ["The SM-X100 mobile phone warranty is 24 months from the date of purchase."]
    merged = tl._merge_terms_results([first, second], PHONE)
    assert merged.duration_months == 24
    assert "SM-X100" in merged.duration_evidence


def test_merge_without_context_uses_first_ranked_source_not_max():
    merged = tl._merge_terms_results(
        [TermsResult(duration_months=12, terms=["a"]), TermsResult(duration_months=60, terms=["b"])]
    )
    assert merged.duration_months == 12


def test_unsure_duration_drops_generated_coverage_line():
    result = TermsResult(
        duration_months=60,
        terms=["Standard coverage for 60 months from purchase date.", "Smart Watches - 60 months"],
        source_url="https://oem.example/mobile",
        duration_candidates=duration_candidates("Smart Watches - 60 months"),
    )
    merged = tl._merge_terms_results([result], PHONE)
    assert merged.duration_months is None
    assert not any(term.startswith("Standard coverage for 60") for term in merged.terms)
