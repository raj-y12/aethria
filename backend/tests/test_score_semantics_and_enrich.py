"""Canonical rubric bands and enrich_scores additive fields."""
from utils.score_semantics import rubric_band_for_int, rubric_band_for_numeric
from utils.scoring import enrich_scores


def test_rubric_band_for_int_matches_v11_buckets():
    assert rubric_band_for_int(2) == "Weak"
    assert rubric_band_for_int(4) == "Concerning"
    assert rubric_band_for_int(6) == "Promising"
    assert rubric_band_for_int(9) == "Strong"


def test_rubric_band_for_numeric_rounds():
    assert rubric_band_for_numeric(6.4) == "Promising"
    assert rubric_band_for_numeric(7.6) == "Strong"


def test_enrich_scores_adds_rubric_bands_without_removing_legacy_labels():
    base = {
        "market_score": 7,
        "product_score": 7,
        "technical_score": 7,
        "execution_score": 7,
        "defensibility_score": 8,
    }
    out = enrich_scores(base)
    assert out["overall_score"] == 7.0
    assert out["overall_label"] == "Strong"  # legacy ladder
    assert out["overall_rubric_band"] == "Promising"  # rubric v1.1
    assert out["market_rubric_band"] == "Promising"
    assert out["defensibility_rubric_band"] == "Strong"
