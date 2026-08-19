"""Regression coverage: ScoutEngine.run_cycle() overwrites confidence with
the deterministic thesis-fit score (product decision, 2026-08-19) --
whatever the model self-reported for "confidence" must never survive into
the stored/gated value."""

from scout.engine import ScoutEngine


def _fake_scout(scout_type="market_driven"):
    class FakeScout:
        def __init__(self):
            self.scout_type = scout_type
            self.system_prompt = "x"

        def set_fund_thesis(self, thesis_ctx):
            pass

        async def _discover_with_validation(self):
            return {
                "id": "raw-id",
                "name": "Acme",
                "sector": "B2B SaaS",
                "funding_stage": "Seed",
                "location": "London, UK",
                "confidence": 0.99,  # the model's self-report -- must be discarded
                "references": ["https://acme.com"],
            }

    return FakeScout()


async def test_run_cycle_overwrites_self_reported_confidence_with_thesis_fit(monkeypatch):
    engine = ScoutEngine(
        api_key="test-key",
        storage=None,
        tenant_user_id="user-test",
        active_thesis={
            "parsed_json": {
                "sectors": ["B2B SaaS"],
                "stage_focus": ["Seed"],
                "geography": ["uk"],
            }
        },
        settings={"agent_config": {"scouts_enabled": True}},
    )
    fake = _fake_scout()
    engine.scouts = [fake]
    monkeypatch.setattr(engine, "_select_scouts_for_wave", lambda: [fake])

    result = await engine.run_cycle(persist_discoveries=False)

    assert len(result.discoveries) == 1
    discovery = result.discoveries[0]
    # All 3 categories matched -> 1.0, not the model's self-reported 0.99.
    assert discovery["confidence"] == 1.0
    assert discovery["thesis_fit"]["matched_categories"] == 3


async def test_run_cycle_scores_zero_confidence_with_no_thesis_match(monkeypatch):
    engine = ScoutEngine(
        api_key="test-key",
        storage=None,
        tenant_user_id="user-test",
        active_thesis={"parsed_json": {"sectors": ["Healthcare"], "stage_focus": ["Series C"], "geography": ["asia"]}},
        settings={"agent_config": {"scouts_enabled": True}},
    )
    fake = _fake_scout()
    engine.scouts = [fake]
    monkeypatch.setattr(engine, "_select_scouts_for_wave", lambda: [fake])

    result = await engine.run_cycle(persist_discoveries=False)

    discovery = result.discoveries[0]
    assert discovery["confidence"] == 0.0
    assert discovery["thesis_fit"]["matched_categories"] == 0
