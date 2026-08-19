"""Regression coverage: triage funnel gate 2 (product direction, 2026-08-18).
Reviewed companies scoring under decision_threshold (default 0.55, i.e. 55%
overall) don't get an automatic Partner decision in run_cycle -- they stay
"reviewed, not decided" until a human requests one explicitly via
run_startup (which has no such gate)."""

from models import ReviewInfo, ScoutInfo
from partner.engine import PartnerEngine
from utils.storage import Storage


def _scout(name: str) -> ScoutInfo:
    return ScoutInfo(
        startup_id=f"s-{name}",
        name=name,
        one_line="Test",
        sector="B2B SaaS",
        problem="p",
        solution="s",
        target_users="u",
        why_now="now",
        scout_type="market_driven",
        confidence_score=0.9,
    )


def _review(*, market: float, product: float, technical: float, execution: float) -> ReviewInfo:
    return ReviewInfo(
        market_score=market,
        product_score=product,
        technical_score=technical,
        execution_score=execution,
        overall_summary="x",
        key_risks=[],
        verdict="MEDIUM",
    )


def _engine(storage: Storage, *, decision_threshold: float | None = None) -> PartnerEngine:
    agent_config = {"partners_enabled": True}
    if decision_threshold is not None:
        agent_config["decision_threshold"] = decision_threshold
    return PartnerEngine(
        storage=storage,
        tenant_user_id="user-test",
        use_llm_fallback=False,
        settings={"agent_config": agent_config},
    )


async def test_below_threshold_entry_is_not_decided(tmp_path):
    storage = Storage(file_path=str(tmp_path / "startups.json"))
    below_id = storage.add_startup(_scout("BelowBar"))
    storage.add_review(below_id, _review(market=4, product=4, technical=4, execution=4))  # avg 4.0/10 = 40%

    engine = _engine(storage)
    result = await engine.run_cycle()

    assert result.succeeded == 0
    startup = storage.get_startup(below_id)
    assert startup.partner_info is None


async def test_above_threshold_entry_is_decided(tmp_path):
    storage = Storage(file_path=str(tmp_path / "startups.json"))
    above_id = storage.add_startup(_scout("AboveBar"))
    storage.add_review(above_id, _review(market=8, product=8, technical=6, execution=6))  # avg 7.0/10 = 70%

    engine = _engine(storage)
    result = await engine.run_cycle()

    assert result.succeeded == 1
    startup = storage.get_startup(above_id)
    assert startup.partner_info is not None


async def test_missing_core_dimension_fails_closed_not_decided(tmp_path):
    """compute_overall_score() requires all 4 core dimensions; missing data
    must never be treated as a passing score (AGENTS.md invariant #5)."""
    storage = Storage(file_path=str(tmp_path / "startups.json"))
    incomplete_id = storage.add_startup(_scout("Incomplete"))
    review = _review(market=9, product=9, technical=9, execution=9)
    review = review.model_copy(update={"execution_score": None})
    storage.add_review(incomplete_id, review)

    engine = _engine(storage)
    result = await engine.run_cycle()

    assert result.succeeded == 0
    startup = storage.get_startup(incomplete_id)
    assert startup.partner_info is None


async def test_decision_threshold_is_configurable_per_tenant(tmp_path):
    storage = Storage(file_path=str(tmp_path / "startups.json"))
    mid_id = storage.add_startup(_scout("MidBar"))
    storage.add_review(mid_id, _review(market=5, product=5, technical=5, execution=5))  # avg 5.0/10 = 50%

    # Default 0.55 would skip this; a lowered tenant override should not.
    engine = _engine(storage, decision_threshold=0.4)
    result = await engine.run_cycle()

    assert result.succeeded == 1
    assert storage.get_startup(mid_id).partner_info is not None


async def test_run_startup_bypasses_the_decision_threshold():
    """The manual override path: run_startup has no decision_threshold gate
    at all, so a human explicitly requesting a decision for one specific
    startup gets one regardless of score -- this IS the "decide anyway" path."""
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        storage = Storage(file_path=f"{tmp}/startups.json")
        below_id = storage.add_startup(_scout("ManualOverride"))
        storage.add_review(below_id, _review(market=2, product=2, technical=2, execution=2))  # avg 2.0/10 = 20%

        engine = _engine(storage)
        decided = await engine.run_startup(below_id)

        assert decided is True
        assert storage.get_startup(below_id).partner_info is not None
