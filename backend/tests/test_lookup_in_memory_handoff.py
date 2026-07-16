import asyncio
from types import SimpleNamespace

from models import PartnerInfo, PartnerSnapshot, ReviewInfo, ScoutInfo, Startup
from partner.engine import PartnerEngine
from reviewer.engine import ReviewerEngine


def _startup():
    return Startup(
        startup_id="handoff-1",
        scout_info=ScoutInfo(
            startup_id="handoff-1",
            name="Handoff",
            one_line="In-memory stages",
            sector="Infra",
            problem="Storage visibility",
            solution="Typed handoff",
            target_users="Funds",
            why_now="Durability",
            scout_type="market_driven",
            confidence_score=0.8,
        ),
        review_info=ReviewInfo(
            market_score=7,
            product_score=7,
            technical_score=7,
            execution_score=7,
            overall_summary="Ready",
            key_risks=[],
            verdict="STRONG",
        ),
        partner_info=PartnerInfo(
            thesis="Ready",
            why_this_matters="Ready",
            snapshot=PartnerSnapshot(one_liner="Ready"),
            market_insight="Ready",
            product_edge="Ready",
            risks=[],
            recommendation="MONITOR",
            decision_rationale="Ready",
            confidence=0.7,
            next_action="Review",
        ),
    )


def test_reviewer_accepts_typed_startup_without_storage_read():
    engine = object.__new__(ReviewerEngine)
    engine.storage = SimpleNamespace(
        get_startup=lambda *_: (_ for _ in ()).throw(AssertionError("storage read"))
    )
    engine.logger = __import__("logging").getLogger("test")

    assert asyncio.run(engine.run_startup("handoff-1", startup=_startup())) is True


def test_partner_accepts_typed_startup_without_storage_read():
    engine = object.__new__(PartnerEngine)
    engine.storage = SimpleNamespace(
        get_startup=lambda *_: (_ for _ in ()).throw(AssertionError("storage read"))
    )
    engine.logger = __import__("logging").getLogger("test")

    assert asyncio.run(engine.run_startup("handoff-1", startup=_startup())) is True
