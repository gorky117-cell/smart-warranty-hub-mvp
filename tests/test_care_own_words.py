"""Step 3 of the own-words run: care tips are SWH's own wording for every product type."""

import pytest

from app.services.product_recommendations import CARE_CATALOG, build_product_recommendations

TYPES = ["smartphone", "laptop", "tv", "fridge", "air_conditioner", "washing_machine", "water_heater", "printer",
         "kitchen_appliance", "fan", "microwave", "purifier", "general"]


@pytest.mark.parametrize("line", TYPES)
def test_every_product_type_has_plain_swh_tips(line):
    tips = CARE_CATALOG[line]
    assert len(tips) >= 3
    for tip in tips:
        text = f"{tip['title']} {tip['why']}"
        assert "OEM" not in text and "official terms" not in text and "coverage promise" not in text
        assert "General care advice" not in text and "General preventive care" not in text


@pytest.mark.parametrize("name,exclusion,title", [
    ("LG Double Door Refrigerator", "Damage from voltage fluctuations is not covered.", "Use a stabilizer or surge protector"),
    ("Sony Bravia TV", "Liquid damage is not covered.", "Keep it away from water"),
    ("Voltas Split AC", "Repairs by unauthorized persons void the warranty.", "Use only authorized service centres"),
])
def test_exclusion_tips_for_any_product(name, exclusion, title):
    recs = build_product_recommendations("u", "w", warranty={"product_name": name, "brand": "Brand", "exclusions": [exclusion],
                                                             "alternatives": {"terms_source_url": "https://example.com"}})
    tip = next(r for r in recs if r["title"] == title)
    assert tip["source_label"] == "From the warranty exclusions"
