from utils.settings_loader import (
    dimension_weights_from_fund_config,
    fund_config_raw_text,
    fund_config_to_thesis_parsed_json,
    load_settings,
    recommendation_for_score_from_fund_config,
    save_settings,
)


def _fund_config():
    return {
        "mandate": {
            "preferredSectors": ["AI Infrastructure"],
            "excludedSectorList": ["Consumer social"],
            "preferredStages": ["Seed"],
            "geographyPreferences": ["US"],
            "thesisText": "Back technical founders in AI infrastructure.",
            "businessModels": "Enterprise usage-based",
            "minimumTraction": "Design partners or early revenue",
        },
        "scoringWeights": [
            {"key": "market", "weight": 20},
            {"key": "product", "weight": 10},
            {"key": "fundFit", "weight": 15},
        ],
        "scoreBands": [
            {"min": 0, "max": 39, "label": "Pass"},
            {"min": 40, "max": 74, "label": "Monitor"},
            {"min": 75, "max": 100, "label": "Strong Proceed"},
        ],
        "risk": {"sensitivity": "conservative"},
        "thresholds": {"partnerReview": 60, "escalation": 75},
    }


def test_fund_config_maps_to_active_thesis_shape():
    parsed = fund_config_to_thesis_parsed_json(_fund_config())
    assert parsed["sectors"] == ["AI Infrastructure"]
    assert parsed["stage_focus"] == ["Seed"]
    assert parsed["geography"] == ["US"]
    assert parsed["exclusions"] == ["Consumer social"]
    assert parsed["risk_profile"] == "conservative"
    assert parsed["source"] == "settings.fund_config"


def test_fund_config_raw_text_and_policy_weights():
    fc = _fund_config()
    raw = fund_config_raw_text(fc)
    assert "ai infrastructure" in raw.lower()
    weights = dimension_weights_from_fund_config(fc)
    assert weights["market"] == 20
    assert weights["product"] == 10
    assert weights["defensibility"] == 15


def test_score_bands_drive_recommendation_mapping():
    fc = _fund_config()
    assert recommendation_for_score_from_fund_config(3.5, fc) == "PASS"
    assert recommendation_for_score_from_fund_config(6.0, fc) == "MONITOR"
    assert recommendation_for_score_from_fund_config(8.0, fc) == "INVEST"


def test_settings_save_and_reload_preserves_fund_config(monkeypatch):
    import utils.settings_loader as settings_mod

    store = {}

    def fake_doc_set(table, data, key, user_id):
        store[(table, key, user_id)] = data

    def fake_doc_get(table, key, user_id):
        return store.get((table, key, user_id))

    monkeypatch.setattr(settings_mod, "doc_set", fake_doc_set)
    monkeypatch.setattr(settings_mod, "doc_get", fake_doc_get)
    settings_mod._SETTINGS_CACHE.clear()

    saved = {"fund_config": _fund_config()}
    save_settings(saved, "user_settings")
    reloaded = load_settings("user_settings", use_cache=False)

    assert reloaded["fund_config"]["mandate"]["preferredSectors"] == ["AI Infrastructure"]
    assert reloaded["fund_config"]["scoreBands"][2]["label"] == "Strong Proceed"
    assert reloaded["fund_config"]["scoringWeights"][0]["key"] == "market"
