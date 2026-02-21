from app.services.kpi_scorecard import (
    brier_score,
    expected_calibration_error,
    percentile,
    population_stability_index,
    safe_pct,
    variant_balance_gap,
)


def test_safe_pct_and_percentile():
    assert safe_pct(2, 4) == 50.0
    assert safe_pct(1, 0) == 0.0
    assert round(percentile([1, 2, 3, 4], 0.5), 3) == 2.5
    assert percentile([], 0.95) == 0.0


def test_brier_and_ece_basic():
    preds = [0.1, 0.2, 0.8, 0.9]
    outs = [0, 0, 1, 1]
    brier = brier_score(preds, outs)
    ece = expected_calibration_error(preds, outs, bins=5)
    assert brier < 0.05
    assert ece < 0.2


def test_psi_and_variant_gap():
    base = [0.1, 0.2, 0.4, 0.6, 0.8]
    now = [0.1, 0.2, 0.45, 0.65, 0.82]
    psi = population_stability_index(base, now, bins=5)
    assert psi < 0.2

    assert variant_balance_gap({"A": 25, "B": 25}) == 0
    assert variant_balance_gap({"A": 26, "B": 24}) == 2
