"""Partner decisions require a current canonical evaluation.

Reviewer scores remain useful qualitative research, but cannot authorize an
automatic or manually-triggered Partner decision on their own.
"""

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


def _engine(storage: Storage) -> PartnerEngine:
    agent_config = {"partners_enabled": True}
    return PartnerEngine(
        storage=storage,
        tenant_user_id="user-test",
        use_llm_fallback=False,
        settings={"agent_config": agent_config},
    )


async def test_reviewer_scores_cannot_authorize_a_cycle_decision(tmp_path):
    storage = Storage(file_path=str(tmp_path / "startups.json"))
    below_id = storage.add_startup(_scout("BelowBar"))
    storage.add_review(below_id, _review(market=4, product=4, technical=4, execution=4))  # avg 4.0/10 = 40%

    engine = _engine(storage)
    result = await engine.run_cycle()

    assert result.succeeded == 0
    startup = storage.get_startup(below_id)
    assert startup.partner_info is None


async def test_high_reviewer_scores_cannot_authorize_a_cycle_decision(tmp_path):
    storage = Storage(file_path=str(tmp_path / "startups.json"))
    above_id = storage.add_startup(_scout("AboveBar"))
    storage.add_review(above_id, _review(market=8, product=8, technical=6, execution=6))  # avg 7.0/10 = 70%

    engine = _engine(storage)
    result = await engine.run_cycle()

    assert result.succeeded == 0
    assert result.blocked == 1
    startup = storage.get_startup(above_id)
    assert startup.partner_info is None


async def test_missing_canonical_evaluation_fails_closed_not_decided(tmp_path):
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


async def test_cycle_never_falls_back_when_canonical_evaluation_is_missing(tmp_path):
    storage = Storage(file_path=str(tmp_path / "startups.json"))
    startup_id = storage.add_startup(_scout("NoCanonicalEvaluation"))
    storage.add_review(startup_id, _review(market=9, product=9, technical=9, execution=9))

    engine = _engine(storage)
    engine.canonical_evaluation_loader = None
    result = await engine.run_cycle()

    assert result.succeeded == 0
    assert result.blocked == 1
    assert storage.get_startup(startup_id).partner_info is None


async def test_cycle_decides_only_from_loaded_canonical_evaluation(tmp_path):
    storage = Storage(file_path=str(tmp_path / "startups.json"))
    startup_id = storage.add_startup(_scout("CanonicalOnly"))
    storage.add_review(startup_id, _review(market=1, product=1, technical=1, execution=1))

    async def load_canonical(_startup_id: str):
        return {
            "recommendation": {"recommended_state": "monitor", "confidence": 0.9},
            "criteria": [
                {"criterion": dimension, "score": 8.0, "evidence_sufficiency": "sufficient"}
                for dimension in ("market", "product", "technical", "execution")
            ],
        }

    engine = _engine(storage)
    engine.canonical_evaluation_loader = load_canonical
    result = await engine.run_cycle()

    assert result.succeeded == 1
    assert storage.get_startup(startup_id).partner_info is not None


async def test_run_startup_requires_canonical_criteria():
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        storage = Storage(file_path=f"{tmp}/startups.json")
        below_id = storage.add_startup(_scout("ManualOverride"))
        storage.add_review(below_id, _review(market=2, product=2, technical=2, execution=2))  # avg 2.0/10 = 20%

        engine = _engine(storage)
        decided = await engine.run_startup(below_id)

        assert decided is False
        assert storage.get_startup(below_id).partner_info is None
