"""Investment read (reviewer_rules v2): founder fluency, capability slope, reframe.

The read is narrative only. These tests pin the two things that make it safe to
ship: it fails closed on thin evidence, and it does not move a score.
"""
import json
from pathlib import Path

from memo_generator import MemoGenerator
from models import Financials, ReviewInfo, ScoutInfo, Startup
from reviewer.base import _build_investment_read_block
from reviewer.schema import normalize_investment_read

REPO_ROOT = Path(__file__).resolve().parents[2]
RULES_DIR = REPO_ROOT / "resources" / "config" / "reviewer_rules"


def _read_payload() -> dict:
    return {
        "founder_fluency": [{
            "founder": "Alex Toussaint",
            "prior_domain": "Guided-weapons control systems at MBDA",
            "fluent_in": ["closed-loop interception under sensor noise"],
            "unlocks": ["defence primes without retraining the team"],
            "evidence": "MBDA guidance engineer, 2017-2023",
        }],
        "capability_slope": {
            "hardest_instance": "Intercepting a moth in free flight by wing-beat sonar",
            "downhill": ["Crop pests, which are larger and fly slower"],
            "blocked_by": ["Export controls on any defence adjacency"],
            "evidence": "Demonstration video, 40g airframe",
        },
        "reframe": {
            "obvious_question": "Is a mosquito-killing drone a real business?",
            "why_it_misleads": "It prices the demo target, not the capability the demo proves.",
            "real_question": "What else can an autonomous interceptor at this size catch?",
        },
    }


def _startup(review_info: ReviewInfo) -> Startup:
    return Startup(
        startup_id="s-1",
        scout_info=ScoutInfo(
            startup_id="s-1",
            name="Tornyol",
            one_line="Autonomous insect interception",
            sector="Robotics",
            problem="Insects.",
            solution="A 40g interceptor drone.",
            target_users="Consumers",
            why_now="Edge inference is cheap.",
            scout_type="market_driven",
            confidence_score=0.7,
        ),
        review_info=review_info,
        financials=Financials(),
    )


def _base_review(**extra) -> ReviewInfo:
    return ReviewInfo(
        market_score=7,
        product_score=7,
        technical_score=8,
        execution_score=6,
        overall_summary="Capable team, unproven market.",
        key_risks=["Consumer pricing"],
        verdict="MEDIUM",
        **extra,
    )


# --- fail closed -----------------------------------------------------------

def test_founder_fluency_drops_founders_identity_did_not_resolve():
    data = _read_payload()
    data["founder_fluency"].append({
        "founder": "Imaginary Cofounder",
        "prior_domain": "Unclear",
        "fluent_in": ["everything"],
        "evidence": "inferred from the company description",
    })

    normalize_investment_read(data, ["Alex Toussaint"])

    assert [entry["founder"] for entry in data["founder_fluency"]] == ["Alex Toussaint"]


def test_founder_fluency_entry_without_evidence_is_dropped():
    data = _read_payload()
    data["founder_fluency"][0].pop("evidence")

    normalize_investment_read(data, ["Alex Toussaint"])

    assert data["founder_fluency"] == []


def test_capability_slope_without_downhill_is_an_ambition_not_a_slope():
    data = _read_payload()
    data["capability_slope"]["downhill"] = []

    normalize_investment_read(data)

    assert data["capability_slope"] == {}


def test_partial_reframe_is_dropped_whole():
    data = _read_payload()
    data["reframe"].pop("real_question")

    normalize_investment_read(data)

    assert data["reframe"] == {}


def test_normalize_is_idempotent():
    data = _read_payload()
    normalize_investment_read(data, ["Alex Toussaint"])
    once = json.dumps(data, sort_keys=True)
    normalize_investment_read(data, ["Alex Toussaint"])

    assert json.dumps(data, sort_keys=True) == once


# --- policy ----------------------------------------------------------------

def test_read_doctrine_is_absent_on_v1_and_present_on_v2():
    v1 = json.loads((RULES_DIR / "v1.json").read_text())
    v2 = json.loads((RULES_DIR / "v2.json").read_text())

    assert _build_investment_read_block(v1) == ""
    block = _build_investment_read_block(v2)
    assert "founder_fluency" in block and "capability_slope" in block and "reframe" in block


def test_only_the_primary_persona_is_given_the_read():
    from reviewer.opportunist import OpportunistReviewer
    from reviewer.reviewer import DefaultReviewer
    from reviewer.skeptical import SkepticalReviewer

    primary = DefaultReviewer(api_key="sk-test")
    assert primary._investment_read_enabled is True
    assert "INVESTMENT READ" in primary.SYSTEM_PROMPT

    for cls in (SkepticalReviewer, OpportunistReviewer):
        persona = cls(api_key="sk-test")
        assert persona._investment_read_enabled is False, cls.__name__
        assert "INVESTMENT READ" not in persona.SYSTEM_PROMPT, cls.__name__


def test_read_does_not_move_a_threshold():
    v1 = json.loads((RULES_DIR / "v1.json").read_text())
    v2 = json.loads((RULES_DIR / "v2.json").read_text())

    assert v2["verdict_thresholds"] == v1["verdict_thresholds"]
    assert v2["diligence_red_flags"] == v1["diligence_red_flags"]


# --- memo ------------------------------------------------------------------

def test_memo_leads_with_the_read_above_the_overview():
    data = _read_payload()
    normalize_investment_read(data, ["Alex Toussaint"])
    memo = MemoGenerator().generate_memo(_startup(_base_review(**data)))

    assert memo.index("## The Read") < memo.index("## Overview")
    assert "What else can an autonomous interceptor at this size catch?" in memo
    assert "Crop pests, which are larger and fly slower" in memo
    assert "MBDA guidance engineer, 2017-2023" in memo


def test_full_memo_names_the_absence_and_display_memo_omits_it():
    startup = _startup(_base_review())

    full = MemoGenerator().generate_memo(startup)
    display = MemoGenerator().generate_memo(startup, for_display=True)

    assert "No read recorded." in full
    assert "## The Read" not in display
