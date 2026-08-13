"""Regional policy rule matching must fail closed.

A rule that narrows on brand/model/category must not apply to a warranty that
does not carry that value. Previously a missing incoming value silently satisfied
the constraint, so a washing-machine rule could apply to a phone with an unknown
category.
"""

from app.db_models import RegionalPolicyDB
from app.services.regional_policy import _match_rule


def _rule(**kwargs) -> RegionalPolicyDB:
    return RegionalPolicyDB(
        region=kwargs.get("region"),
        brand=kwargs.get("brand"),
        model_code=kwargs.get("model_code"),
        product_type=kwargs.get("product_type"),
        rule_json=kwargs.get("rule_json") or {},
        active=1,
    )


def test_category_scoped_rule_matches_same_category():
    rule = _rule(region="IN", product_type="washing_machine")
    assert _match_rule(
        rule,
        region="IN",
        brand="Samsung",
        model_code="WA65A4002VS",
        product_type="washing_machine",
    ) is True


def test_category_scoped_rule_does_not_match_other_category():
    rule = _rule(region="IN", product_type="washing_machine")
    assert _match_rule(
        rule,
        region="IN",
        brand="Samsung",
        model_code="SM-M176B",
        product_type="smartphone",
    ) is False


def test_category_scoped_rule_does_not_match_unknown_category():
    """Fail closed: unknown category must not inherit a category-specific rule."""
    rule = _rule(region="IN", product_type="washing_machine")
    assert _match_rule(
        rule, region="IN", brand=None, model_code=None, product_type=None
    ) is False
    assert _match_rule(
        rule, region="IN", brand=None, model_code=None, product_type="general"
    ) is False


def test_brand_scoped_rule_does_not_match_missing_brand():
    rule = _rule(region="IN", brand="Samsung")
    assert _match_rule(
        rule, region="IN", brand=None, model_code=None, product_type="smartphone"
    ) is False


def test_model_scoped_rule_does_not_match_missing_model():
    rule = _rule(region="IN", model_code="WA65A4002VS")
    assert _match_rule(
        rule, region="IN", brand="Samsung", model_code=None, product_type="washing_machine"
    ) is False


def test_region_only_rule_applies_to_any_product_in_region():
    """A rule with no narrowing still applies region-wide, as intended."""
    rule = _rule(region="IN")
    assert _match_rule(
        rule, region="IN", brand="Samsung", model_code="SM-M176B", product_type="smartphone"
    ) is True
    assert _match_rule(
        rule, region="IN", brand=None, model_code=None, product_type=None
    ) is True


def test_region_mismatch_never_applies():
    rule = _rule(region="IN", product_type="washing_machine")
    assert _match_rule(
        rule, region="UK", brand="Samsung", model_code="WA65A4002VS", product_type="washing_machine"
    ) is False
