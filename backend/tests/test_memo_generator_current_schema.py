from memo_generator import MemoGenerator
from models import Financials, PartnerInfo, PartnerSnapshot, ReviewInfo, ScoutInfo, Startup
from utils.storage import Storage


def _decided_startup() -> Startup:
    return Startup(
        startup_id="startup-1",
        scout_info=ScoutInfo(
            startup_id="startup-1",
            name="Acme",
            one_line="AI infrastructure for factories",
            sector="Industrial AI",
            problem="Factory data is fragmented.",
            solution="A unified operating layer.",
            target_users="Manufacturing teams",
            why_now="Edge inference is economical.",
            scout_type="market_driven",
            confidence_score=0.8,
            references=["https://acme.example"],
        ),
        review_info=ReviewInfo(
            market_score=8,
            product_score=7,
            technical_score=7,
            execution_score=6,
            overall_summary="Promising company with execution risk.",
            key_risks=["Long sales cycles"],
            verdict="STRONG",
        ),
        partner_info=PartnerInfo(
            thesis="Industrial intelligence",
            why_this_matters="Large underserved market",
            snapshot=PartnerSnapshot(one_liner="Factory intelligence layer"),
            market_insight="Legacy systems are difficult to integrate.",
            product_edge="Fast deployment",
            risks=["Enterprise sales"],
            recommendation="MONITOR",
            decision_rationale="Evidence is promising but early.",
            confidence=0.72,
            next_action="Revisit after three more deployments",
            human_review_required=True,
        ),
        financials=Financials(),
    )


def test_internal_memo_uses_current_partner_info_schema():
    memo = MemoGenerator().generate_memo(_decided_startup())

    assert "**Investment decision:** MONITOR" in memo
    assert "**Confidence:** 72%" in memo
    assert "Evidence is promising but early." in memo


def test_summary_uses_current_partner_info_schema():
    summary = MemoGenerator().generate_summary(_decided_startup())

    assert "**Decision:** MONITOR (Confidence: 72%)" in summary
    assert "Human review required" in summary


def test_local_storage_filters_decisions_by_canonical_or_legacy_code(tmp_path):
    storage = Storage(str(tmp_path / "startups.json"))
    startup = _decided_startup()
    storage.add_startup(startup.scout_info)
    storage.add_review(startup.startup_id, startup.review_info)
    storage.add_partner_decision(startup.startup_id, startup.partner_info)

    assert [s.startup_id for s in storage.get_startups_with_decision("MONITOR")] == ["startup-1"]
    assert [s.startup_id for s in storage.get_startups_with_decision("MAYBE")] == ["startup-1"]


def test_local_storage_duplicate_name_returns_existing_startup_id(tmp_path):
    storage = Storage(str(tmp_path / "startups.json"))
    existing = _decided_startup().scout_info
    storage.add_startup(existing)
    duplicate = existing.model_copy(update={"startup_id": "new-unused-id"})

    assert storage.add_startup(duplicate) == "startup-1"
    assert [s.startup_id for s in storage.get_all_startups()] == ["startup-1"]
