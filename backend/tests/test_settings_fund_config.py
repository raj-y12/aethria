import pytest

from utils.settings_loader import (
    dimension_weights_from_fund_config,
    fund_config_content_changed,
    fund_config_content_fingerprint,
    fund_config_matches_thesis_payload,
    fund_config_raw_text,
    fund_config_to_thesis_parsed_json,
    reconcile_fund_config_with_thesis,
    recommendation_for_score_from_fund_config,
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


def test_reconcile_fund_config_uses_active_thesis_as_canonical_content():
    stored = _fund_config()
    stored["version"] = 34
    stored["mandate"]["preferredSectors"] = ["Old sector"]
    stored["mandate"]["thesisText"] = ""
    active = {
        "sectors": ["AI", "Infrastructure"],
        "stage_focus": ["Seed", "Series A"],
        "geography": ["Europe", "US"],
        "exclusions": ["Crypto"],
        "risk_profile": "balanced",
        "check_size_min": 100000,
        "check_size_max": 2000000,
        "ownership_target": 10,
        "score_bands": [{"min": 75, "max": 100, "label": "Invest"}],
        "scoring_weights": [{"key": "market", "weight": 30}],
        "rubric": [{"key": "market", "label": "Market"}],
        "thresholds": {"partnerReview": 61},
    }

    reconciled = reconcile_fund_config_with_thesis(
        stored,
        raw_text="canonical thesis",
        parsed_json=active,
        version_number=37,
        version_id="version-37",
    )

    assert reconciled["version"] == 37
    assert reconciled["versionLabel"] == "Fund Thesis v37"
    assert reconciled["activePolicyVersionId"] == "version-37"
    assert reconciled["mandate"]["preferredSectors"] == ["AI", "Infrastructure"]
    assert reconciled["mandate"]["excludedSectorList"] == ["Crypto"]
    assert reconciled["mandate"]["excludedSectors"] == ["Crypto"]
    assert reconciled["mandate"]["checkSizeMin"] == 100000
    assert reconciled["mandate"]["checkSizeMax"] == 2000000
    assert reconciled["risk"]["sensitivity"] == "balanced"
    assert reconciled["scoreBands"] == active["score_bands"]
    assert reconciled["scoringWeights"] == active["scoring_weights"]
    assert reconciled["rubric"] == active["rubric"]
    assert reconciled["thresholds"] == active["thresholds"]


def test_published_mandate_signal_distinguishes_user_config_from_default():
    """The onboarding gate keys off parsed_json.is_default: the bootstrap default
    carries it, a user-published fund_config must not."""
    from fund_thesis import DEFAULT_THESIS_PARSED_JSON

    assert DEFAULT_THESIS_PARSED_JSON.get("is_default") is True
    user_parsed = fund_config_to_thesis_parsed_json(_fund_config())
    assert not user_parsed.get("is_default")


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


@pytest.mark.asyncio
async def test_settings_save_and_reload_preserves_fund_config():
    import utils.settings_loader as settings_mod

    class Repository:
        def __init__(self):
            self.store = {}

        async def get(self, user_id, *, key=None):
            return self.store.get((user_id, key))

        async def upsert(self, user_id, data, *, key=None):
            self.store[(user_id, key)] = data

    repository = Repository()
    settings_mod._SETTINGS_CACHE.clear()

    saved = {"fund_config": _fund_config()}
    await settings_mod.save_settings(saved, "user_settings", repository=repository)
    reloaded = await settings_mod.load_settings(
        "user_settings", repository=repository, use_cache=False
    )

    assert reloaded["fund_config"]["mandate"]["preferredSectors"] == ["AI Infrastructure"]
    assert reloaded["fund_config"]["scoreBands"][2]["label"] == "Strong Proceed"
    assert reloaded["fund_config"]["scoringWeights"][0]["key"] == "market"


@pytest.mark.asyncio
async def test_runtime_limits_load_from_saved_settings(monkeypatch):
    import utils.settings_loader as settings_mod

    async def load_settings(*_args, **_kwargs):
        return {
            "agent_config": {"max_agents_per_run": 2},
            "cost_budget": {
                "enabled": True,
                "max_tokens_per_run": 321,
                "cooldown_seconds": 7,
                "daily_cost_ceiling": 0.25,
            },
        }

    monkeypatch.setattr(settings_mod, "load_settings", load_settings)
    limits = await settings_mod.get_runtime_limits("user_settings")

    assert limits["max_agents_per_run"] == 2
    assert limits["max_tokens_per_run"] == 321
    assert limits["cooldown_seconds"] == 7
    assert limits["daily_cost_ceiling"] == 0.25


def test_sync_fund_config_to_active_thesis_validates_user_id_without_name_error(monkeypatch):
    import fund_thesis
    from fund_thesis import sync_fund_config_to_active_thesis

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


def test_sync_fund_config_does_not_block_settings_deploy_on_embedding(monkeypatch):
    import fund_thesis
    import fund_thesis.ops as fund_thesis_ops
    from fund_thesis import sync_fund_config_to_active_thesis

    calls = []
    monkeypatch.setattr(fund_thesis, "get_active_thesis", lambda client, user_id: None)

    def fake_create(client, **kwargs):
        calls.append(kwargs)
        return {"version_id": "version_1", "version_number": 1, "skipped": False}

    monkeypatch.setattr(fund_thesis_ops, "create_fund_thesis_version_for_user", fake_create)

    result = sync_fund_config_to_active_thesis(
        object(), user_id="new_user", fund_config=_fund_config(), api_key="configured"
    )

    assert result["version_id"] == "version_1"
    assert calls[0]["skip_embedding"] is True
