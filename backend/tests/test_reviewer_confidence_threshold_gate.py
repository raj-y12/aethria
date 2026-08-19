"""Regression coverage: triage funnel gate 1 (product direction, 2026-08-18).
Scout candidates scoring under confidence_threshold (default 0.3, i.e. 30%
confidence) don't get reviewed in run_cycle -- they stay "not reviewed"
forever unless a human requests one explicitly via run_startup with
ignore_confidence_threshold=True (the "review it anyway" manual override)."""

from unittest.mock import AsyncMock, patch

from models import ReviewInfo, ScoutInfo
from reviewer.engine import ReviewerEngine
from utils.storage import Storage


def _scout(name: str, confidence: float) -> ScoutInfo:
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
        confidence_score=confidence,
    )


def _fake_review_result() -> dict:
    return ReviewInfo(
        market_score=8,
        product_score=8,
        technical_score=8,
        execution_score=8,
        overall_summary="x",
        key_risks=[],
        verdict="MEDIUM",
    ).model_dump()


def _engine(storage: Storage, *, confidence_threshold: float | None = None) -> ReviewerEngine:
    agent_config = {"reviewers_enabled": True}
    if confidence_threshold is not None:
        agent_config["confidence_threshold"] = confidence_threshold
    return ReviewerEngine(
        api_key="test-key",
        storage=storage,
        tenant_user_id="user-test",
        settings={"agent_config": agent_config},
    )


async def test_below_default_threshold_entry_is_not_reviewed(tmp_path):
    storage = Storage(file_path=str(tmp_path / "startups.json"))
    below_id = storage.add_startup(_scout("BelowBar", confidence=0.25))  # 25% < 30% default

    engine = _engine(storage)
    with patch.object(ReviewerEngine, "_review_personas", new=AsyncMock(return_value=[_fake_review_result()] * 3)):
        result = await engine.run_cycle()

    assert result.succeeded == 0
    assert storage.get_startup(below_id).review_info is None


async def test_above_default_threshold_entry_is_reviewed(tmp_path):
    storage = Storage(file_path=str(tmp_path / "startups.json"))
    above_id = storage.add_startup(_scout("AboveBar", confidence=0.5))  # 50% > 30% default

    engine = _engine(storage)
    with patch.object(ReviewerEngine, "_review_personas", new=AsyncMock(return_value=[_fake_review_result()] * 3)):
        result = await engine.run_cycle()

    assert result.succeeded == 1
    assert storage.get_startup(above_id).review_info is not None


async def test_confidence_threshold_is_configurable_per_tenant(tmp_path):
    storage = Storage(file_path=str(tmp_path / "startups.json"))
    mid_id = storage.add_startup(_scout("MidBar", confidence=0.28))  # below default 0.3

    # A lowered tenant override should let this through.
    engine = _engine(storage, confidence_threshold=0.2)
    with patch.object(ReviewerEngine, "_review_personas", new=AsyncMock(return_value=[_fake_review_result()] * 3)):
        result = await engine.run_cycle()

    assert result.succeeded == 1
    assert storage.get_startup(mid_id).review_info is not None


async def test_run_startup_can_bypass_the_confidence_threshold(tmp_path):
    """The manual override path: run_startup(ignore_confidence_threshold=True)
    is the "review it anyway" action for a human-triggered snapshot decision."""
    storage = Storage(file_path=str(tmp_path / "startups.json"))
    below_id = storage.add_startup(_scout("ManualOverride", confidence=0.1))  # 10%, far below bar

    engine = _engine(storage)
    with patch.object(ReviewerEngine, "_review_personas", new=AsyncMock(return_value=[_fake_review_result()] * 3)):
        reviewed = await engine.run_startup(below_id, ignore_confidence_threshold=True)

    assert reviewed is True
    assert storage.get_startup(below_id).review_info is not None
