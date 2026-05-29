from utils.settings_loader import (
    dimension_weights_from_fund_config,
    fund_config_content_changed,
    fund_config_content_fingerprint,
    fund_config_matches_thesis_payload,
    fund_config_raw_text,
    fund_config_to_thesis_parsed_json,
    load_settings,
    recommendation_for_score_from_fund_config,
    save_settings,
    thesis_payload_fingerprint,
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


def test_fund_config_content_fingerprint_ignores_version_metadata():
    base = _fund_config()
    bumped = {**base, "version": 99, "versionLabel": "Fund Thesis v99", "lastSavedAt": "now"}
    assert fund_config_content_fingerprint(base) == fund_config_content_fingerprint(bumped)
    assert not fund_config_content_changed(base, bumped)


def test_fund_config_content_changed_detects_mandate_edit():
    base = _fund_config()
    edited = {**base, "mandate": {**base["mandate"], "thesisText": "Different mandate."}}
    assert fund_config_content_changed(base, edited)


def test_fund_config_matches_thesis_payload():
    fc = _fund_config()
    raw = fund_config_raw_text(fc)
    parsed = fund_config_to_thesis_parsed_json(fc)
    assert fund_config_matches_thesis_payload(raw_text=raw, parsed_json=parsed, fund_config=fc)
    other_fp = thesis_payload_fingerprint(raw_text=raw + "\nextra", parsed_json=parsed)
    assert other_fp != thesis_payload_fingerprint(raw_text=raw, parsed_json=parsed)


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
    assert "traction" not in weights
    assert "timing" not in weights


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


def test_runtime_limits_load_from_saved_settings(monkeypatch):
    import utils.settings_loader as settings_mod

    monkeypatch.setattr(
        settings_mod,
        "load_settings",
        lambda user_id=None, use_cache=True: {
            "agent_config": {"max_agents_per_run": 2},
            "cost_budget": {
                "enabled": True,
                "max_tokens_per_run": 321,
                "cooldown_seconds": 7,
                "daily_cost_ceiling": 0.25,
            },
        },
    )

    limits = settings_mod.get_runtime_limits("user_settings")

    assert limits["max_agents_per_run"] == 2
    assert limits["max_tokens_per_run"] == 321
    assert limits["cooldown_seconds"] == 7
    assert limits["daily_cost_ceiling"] == 0.25


def test_sync_fund_config_to_active_thesis_validates_user_id_without_name_error(monkeypatch):
    import fund_thesis
    from fund_thesis_ops import sync_fund_config_to_active_thesis

    fc = _fund_config()
    raw = fund_config_raw_text(fc)
    parsed = fund_config_to_thesis_parsed_json(fc)

    class ActiveThesis:
        raw_text = raw
        parsed_json = parsed
        thesis_id = "thesis_1"
        version_id = "version_1"
        version_number = 1

    monkeypatch.setattr(fund_thesis, "get_active_thesis", lambda client, user_id: ActiveThesis())

    result = sync_fund_config_to_active_thesis(
        object(),
        user_id="user_settings",
        fund_config=fc,
    )

    assert result["skipped"] is True
    assert result["version_id"] == "version_1"
