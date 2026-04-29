from services.scoring.normalization_layer import (
    normalize_architecture,
    normalize_barriers,
    normalize_brand,
    normalize_complexity,
    normalize_competition,
    normalize_data_advantage,
    normalize_differentiation,
    normalize_engineering_quality,
    normalize_growth_velocity,
    normalize_gtm,
    normalize_network_effects,
    normalize_operational_velocity,
    normalize_pain_alignment,
    normalize_proprietary_data,
    normalize_retention,
    normalize_scalability,
    normalize_switching_costs,
    normalize_team_execution,
    normalize_traction,
    normalize_ux,
    normalize_value_prop,
    normalize_growth,
    normalize_tam,
    normalize_timing,
    normalize_urgency,
)


def test_normalize_tam_extremes():
    assert normalize_tam("$25B") >= 9.0
    assert normalize_tam("$50M") <= 5.0


def test_normalize_growth_extremes():
    assert normalize_growth("65%") == 10.0
    assert normalize_growth("2%") <= 4.5


def test_normalize_label_defaults_and_mapping():
    assert normalize_urgency(None) == 5.0
    assert normalize_timing("favorable") >= 7.5
    assert normalize_competition("crowded") <= 5.0


def test_execution_normalizers():
    assert normalize_traction("scaling") == 8
    assert normalize_growth_velocity("hyper") == 10
    assert normalize_gtm("repeatable") == 8
    assert normalize_team_execution("elite") == 10
    assert normalize_operational_velocity("moderate") == 6


def test_product_normalizers():
    assert normalize_value_prop("clear") == 8
    assert normalize_pain_alignment("critical") == 10
    assert normalize_differentiation("none") == 2
    assert normalize_ux("smooth") == 8
    assert normalize_retention("missing") == 5


def test_technical_normalizers():
    assert normalize_complexity("deeptech") == 10
    assert normalize_engineering_quality("decent") == 6
    assert normalize_scalability("extreme") == 10
    assert normalize_data_advantage("limited") == 5
    assert normalize_architecture("robust") == 10


def test_defensibility_normalizers():
    assert normalize_network_effects("moderate") == 7
    assert normalize_switching_costs("very_high") == 10
    assert normalize_proprietary_data("none") == 2
    assert normalize_barriers("hard") == 8
    assert normalize_brand("leader") == 10
