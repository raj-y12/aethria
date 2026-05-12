from types import SimpleNamespace

from partner.decision import PartnerDecisionEngine


def _base_scout():
    return {
        "name": "Sona",
        "one_line": "AI-driven ops insights",
        "sector": "B2B SaaS",
        "funding_stage": "Seed",
        "confidence": 0.8,
    }


def _base_review():
    return {
        "verdict": "MEDIUM",
        "market_score": 7,
        "product_score": 6,
        "technical_score": 6,
        "execution_score": 6,
        "defensibility_score": None,
        "score_reasoning": {},
        "key_risks": [],
        "assumption_feedback": [],
        "team_analysis": ["Experienced founder with prior exit."],
        "business_model_analysis": ["Clear B2B SaaS pricing with gross-margin potential."],
        "thesis_alignment_score": 0.7,
    }


def test_medium_6_4_borderline_routes_to_llm():
    engine = PartnerDecisionEngine(use_llm_fallback=True, api_key=None)
    review = _base_review()
    review.update(
        {
            "market_score": 7,
            "product_score": 7,
            "technical_score": 6,
            "execution_score": 6,
            "defensibility_score": 6,
        }
    )  # Core-dim avg = 6.5 → canonical MONITOR; borderline bucket triggers LLM then alignment.

    llm_kwargs: dict = {}

    def fake_llm(*args, **kwargs):
        llm_kwargs.update(kwargs)
        return engine._create_decision(
            decision="MAYBE",
            confidence=6,
            rationale="LLM rationale",
            next_action="Monitor market and track progress",
            human_review_required=True,
            assumption_risks=[],
        )

    engine._decide_with_llm = fake_llm  # type: ignore[method-assign]
    out = engine.decide(_base_scout(), review)
    assert llm_kwargs.get("final_recommendation") == "MONITOR"
    assert out.get("decision") == "MAYBE"
    rl = (out.get("rationale") or "").lower()
    assert "we monitor at this stage" in rl
    assert out.get("decision_drivers")


def test_medium_5_8_near_threshold_routes_to_llm():
    engine = PartnerDecisionEngine(use_llm_fallback=True, api_key=None)
    review = _base_review()
    review.update(
        {
            "market_score": 6,
            "product_score": 6,
            "technical_score": 6,
            "execution_score": 5,
            "defensibility_score": 6,
        }
    )  # Core-dim avg = 5.75 (< pass bar): canonical PASS; near-threshold still escalates to LLM.

    llm_kwargs: dict = {}

    def fake_llm(*args, **kwargs):
        llm_kwargs.update(kwargs)
        return engine._create_decision(
            decision="MAYBE",
            confidence=5,
            rationale="Near-threshold LLM rationale",
            next_action="Human review required - monitor closely",
            human_review_required=True,
            assumption_risks=[],
        )

    engine._decide_with_llm = fake_llm  # type: ignore[method-assign]
    out = engine.decide(_base_scout(), review)
    assert llm_kwargs.get("final_recommendation") == "PASS"
    assert out.get("decision") == "NO"
    rl = (out.get("rationale") or "").lower()
    assert "we pass at this stage" in rl
    assert "near-threshold llm rationale" not in rl


def test_hard_low_score_stays_deterministic_no():
    engine = PartnerDecisionEngine(use_llm_fallback=True, api_key=None)
    review = _base_review()
    review.update(
        {
            "market_score": 5,
            "product_score": 5,
            "technical_score": 5,
            "execution_score": 5,
        }
    )  # avg = 5.0
    out = engine.decide(_base_scout(), review)
    assert out.get("decision") == "NO"
    assert "minimum pass threshold" in (out.get("rationale") or "").lower()


def test_saved_score_bands_drive_partner_recommendation(monkeypatch):
    import partner.decision as decision_mod

    monkeypatch.setattr(
        decision_mod,
        "load_settings",
        lambda user_id: {
            "fund_config": {
                "scoreBands": [
                    {"min": 0, "max": 49, "label": "Pass"},
                    {"min": 50, "max": 69, "label": "Monitor"},
                    {"min": 70, "max": 100, "label": "Strong Proceed"},
                ],
                "thresholds": {"partnerReview": 50, "monitor": 50, "escalation": 70, "autoPass": 49},
            }
        },
    )
    engine = PartnerDecisionEngine(use_llm_fallback=False, api_key=None, tenant_user_id="user_123")
    review = _base_review()
    review.update(
        {
            "market_score": 7,
            "product_score": 7,
            "technical_score": 7,
            "execution_score": 7,
            "derived_verdict": "STRONG",
        }
    )
    out = engine.decide(_base_scout(), review)
    assert out.get("recommendation") == "INVEST"
    assert out.get("decision") == "YES"


def test_weak_verdict_uses_constructive_pass_rationale():
    engine = PartnerDecisionEngine(use_llm_fallback=False, api_key=None)
    review = _base_review()
    review.update(
        {
            "verdict": "WEAK",
            "market_score": 4,
            "product_score": 4,
            "technical_score": 4,
            "execution_score": 4,
        }
    )

    out = engine.decide(_base_scout(), review)
    rationale = out.get("rationale") or ""

    assert out.get("decision") == "NO"
    assert "we pass at this stage given cautious reviewer quality" in rationale.lower()
    assert "not suitable for investment consideration" not in rationale.lower()


def test_critical_risk_pass_uses_actionable_language():
    engine = PartnerDecisionEngine(use_llm_fallback=False, api_key=None)
    review = _base_review()
    review.update(
        {
            "verdict": "MEDIUM",
            "market_score": 7,
            "product_score": 7,
            "technical_score": 6,
            "execution_score": 6,
            "key_risks": ["Regulatory ban risk in primary market"],
        }
    )

    out = engine.decide(_base_scout(), review)
    rationale = (out.get("rationale") or "").lower()

    assert out.get("decision") == "MAYBE"
    assert "we monitor at this stage" in rationale
    assert "material diligence risks" in rationale
    assert "risk too high for investment" not in rationale


def test_monitor_and_invest_paths_use_consistent_professional_tone():
    engine = PartnerDecisionEngine(use_llm_fallback=False, api_key=None)

    monitor_review = _base_review()
    monitor_review.update(
        {
            "verdict": "MEDIUM",
            "market_score": 7,
            "product_score": 7,
            "technical_score": 7,
            "execution_score": 7,
            "defensibility_score": None,
        }
    )  # avg = 7.0, deterministic MONITOR
    monitor_out = engine.decide(_base_scout(), monitor_review)
    monitor_rationale = (monitor_out.get("rationale") or "").lower()
    assert monitor_out.get("decision") == "MAYBE"
    assert "we monitor at this stage" in monitor_rationale
    assert (
        "constructive averages" in monitor_rationale
        or "grey zone" in monitor_rationale
    )

    invest_review = _base_review()
    invest_review.update(
        {
            "verdict": "STRONG",
            "market_score": 8,
            "product_score": 8,
            "technical_score": 8,
            "execution_score": 8,
            "defensibility_score": None,
        }
    )  # avg = 8.0, deterministic INVEST
    invest_out = engine.decide(_base_scout(), invest_review)
    invest_rationale = (invest_out.get("rationale") or "").lower()
    assert invest_out.get("decision") == "YES"
    assert "confirmatory diligence" in invest_rationale


def test_empty_llm_content_generates_non_generic_rationale():
    engine = PartnerDecisionEngine(use_llm_fallback=True, api_key="fake-key")

    empty_message = SimpleNamespace(content="")
    empty_choice = SimpleNamespace(message=empty_message, finish_reason="stop")
    empty_usage = SimpleNamespace(prompt_tokens=1, completion_tokens=1, total_tokens=2)
    empty_response = SimpleNamespace(choices=[empty_choice], usage=empty_usage)

    class _FakeCompletions:
        def create(self, *args, **kwargs):
            return empty_response

    class _FakeChat:
        completions = _FakeCompletions()

    class _FakeClient:
        chat = _FakeChat()

    engine.client = _FakeClient()  # type: ignore[assignment]
    review = _base_review()
    out = engine._decide_with_llm(
        _base_scout(),
        review,
        assumption_risks=[],
        trigger_reason="MEDIUM verdict with borderline average score",
        avg_score=6.25,
        final_recommendation="MONITOR",
    )
    rationale = out.get("rationale") or ""
    assert out.get("decision") == "MAYBE"
    rl = rationale.lower()
    assert (
        "unable to render a full response" in rl
        or "llm call failed or returned invalid output" in rl
        or "llm edge-case decision" in rl
    )


def test_threshold_boundary_6_0_does_not_use_low_score_llm_path():
    engine = PartnerDecisionEngine(use_llm_fallback=False, api_key=None)
    review = _base_review()
    review.update(
        {
            "market_score": 6,
            "product_score": 6,
            "technical_score": 6,
            "execution_score": 6,
        }
    )  # avg = 6.0
    out = engine.decide(_base_scout(), review)
    assert out.get("decision") in ("NO", "MAYBE")
    assert "below our minimum pass threshold" not in (out.get("rationale") or "").lower()


def test_threshold_boundary_7_0_not_in_borderline_bucket():
    engine = PartnerDecisionEngine(use_llm_fallback=False, api_key=None)
    review = _base_review()
    review.update(
        {
            "market_score": 7,
            "product_score": 7,
            "technical_score": 7,
            "execution_score": 7,
        }
    )  # avg = 7.0
    out = engine.decide(_base_scout(), review)
    assert out.get("decision") in ("MAYBE", "NO")
    assert "borderline case" not in (out.get("rationale") or "").lower()


def test_contradictory_scores_trigger_llm():
    engine = PartnerDecisionEngine(use_llm_fallback=True, api_key=None)
    review = _base_review()
    review.update(
        {
            "market_score": 9,
            "product_score": 8,
            "technical_score": 4,
            "execution_score": 7,
            "defensibility_score": None,
        }
    )

    llm_kwargs: dict = {}

    def fake_llm(*args, **kwargs):
        llm_kwargs.update(kwargs)
        return engine._create_decision(
            decision="MAYBE",
            confidence=6,
            rationale="Contradiction handled",
            next_action="Human review required - monitor closely",
            human_review_required=True,
            assumption_risks=[],
        )

    engine._decide_with_llm = fake_llm  # type: ignore[method-assign]
    out = engine.decide(_base_scout(), review)
    assert llm_kwargs.get("final_recommendation") == "MONITOR"
    rl = (out.get("rationale") or "").lower()
    assert "contradiction handled" not in rl
    assert "we monitor at this stage" in rl
    assert "material tension" in rl or "mixed signals" in rl


def test_use_llm_fallback_false_forces_deterministic_path():
    engine = PartnerDecisionEngine(use_llm_fallback=False, api_key=None)
    review = _base_review()
    review.update(
        {
            "market_score": 9,
            "product_score": 8,
            "technical_score": 4,
            "execution_score": 7,
        }
    )
    out = engine.decide(_base_scout(), review)
    rl = (out.get("rationale") or "").lower()
    assert "contradiction handled" not in rl
    assert "we monitor at this stage" in rl


def test_missing_assumptions_trigger_llm():
    engine = PartnerDecisionEngine(use_llm_fallback=True, api_key=None)
    review = _base_review()
    review["assumption_feedback"] = ["Critical unknown: GTM channel conversion not validated"]

    llm_kwargs: dict = {}

    def fake_llm(*args, **kwargs):
        llm_kwargs.update(kwargs)
        return engine._create_decision(
            decision="MAYBE",
            confidence=5,
            rationale="Assumption-risk escalation",
            next_action="Human review required - monitor closely",
            human_review_required=True,
            assumption_risks=[],
        )

    engine._decide_with_llm = fake_llm  # type: ignore[method-assign]
    out = engine.decide(_base_scout(), review)
    assert llm_kwargs.get("final_recommendation") == "MONITOR"
    rl = (out.get("rationale") or "").lower()
    assert "assumption-risk escalation" not in rl
    assert "we monitor at this stage" in rl


def test_missing_critical_qualitative_triggers_llm():
    engine = PartnerDecisionEngine(use_llm_fallback=True, api_key=None)
    review = _base_review()
    review["team_analysis"] = []
    review["business_model_analysis"] = []

    llm_kwargs: dict = {}

    def fake_llm(*args, **kwargs):
        llm_kwargs.update(kwargs)
        return engine._create_decision(
            decision="MAYBE",
            confidence=5,
            rationale="Qualitative-gap escalation",
            next_action="Human review required - monitor closely",
            human_review_required=True,
            assumption_risks=[],
        )

    engine._decide_with_llm = fake_llm  # type: ignore[method-assign]
    out = engine.decide(_base_scout(), review)
    assert llm_kwargs.get("final_recommendation") == "MONITOR"
    rl = (out.get("rationale") or "").lower()
    assert "qualitative-gap escalation" not in rl
    assert "we monitor at this stage" in rl


def test_reviewer_disagreement_trigger_llm():
    engine = PartnerDecisionEngine(use_llm_fallback=True, api_key=None)
    # Ensure policy enables this trigger for the test.
    engine._rules.setdefault("llm_fallback_triggers", {})["reviewer_disagreement"] = True
    review = _base_review()
    review["reviewer_disagreement"] = True

    llm_kwargs: dict = {}

    def fake_llm(*args, **kwargs):
        llm_kwargs.update(kwargs)
        return engine._create_decision(
            decision="MAYBE",
            confidence=5,
            rationale="Reviewer-disagreement escalation",
            next_action="Human review required - monitor closely",
            human_review_required=True,
            assumption_risks=[],
        )

    engine._decide_with_llm = fake_llm  # type: ignore[method-assign]
    out = engine.decide(_base_scout(), review)
    assert llm_kwargs.get("final_recommendation") == "MONITOR"
    rl = (out.get("rationale") or "").lower()
    assert "reviewer-disagreement escalation" not in rl
    assert "we monitor at this stage" in rl


def test_high_thesis_alignment_trigger_llm():
    engine = PartnerDecisionEngine(use_llm_fallback=True, api_key=None)
    review = _base_review()
    review["market_score"] = 8
    review["product_score"] = 8
    review["technical_score"] = 7
    review["execution_score"] = 7
    review["thesis_alignment_score"] = 0.9

    llm_kwargs: dict = {}

    def fake_llm(*args, **kwargs):
        llm_kwargs.update(kwargs)
        return engine._create_decision(
            decision="MAYBE",
            confidence=6,
            rationale="High-thesis escalation",
            next_action="Monitor market and track progress",
            human_review_required=True,
            assumption_risks=[],
        )

    engine._decide_with_llm = fake_llm  # type: ignore[method-assign]
    out = engine.decide(_base_scout(), review)
    assert llm_kwargs.get("final_recommendation") == "MONITOR"
    rl = (out.get("rationale") or "").lower()
    assert "high-thesis escalation" not in rl
    assert "we monitor at this stage" in rl


def test_openai_exception_returns_safe_maybe_with_contextual_rationale():
    engine = PartnerDecisionEngine(use_llm_fallback=True, api_key="fake-key")

    class _BoomCompletions:
        def create(self, *args, **kwargs):
            raise RuntimeError("boom")

    class _BoomChat:
        completions = _BoomCompletions()

    class _BoomClient:
        chat = _BoomChat()

    engine.client = _BoomClient()  # type: ignore[assignment]
    out = engine._decide_with_llm(
        _base_scout(),
        _base_review(),
        assumption_risks=[],
        trigger_reason="MEDIUM verdict with borderline average score",
        avg_score=6.25,
        final_recommendation="MONITOR",
    )
    assert out.get("decision") == "MAYBE"
    assert "average score" in (out.get("rationale") or "").lower()


def test_malformed_json_returns_safe_maybe():
    engine = PartnerDecisionEngine(use_llm_fallback=True, api_key="fake-key")
    bad_message = SimpleNamespace(content="this is not json")
    bad_choice = SimpleNamespace(message=bad_message, finish_reason="stop")
    bad_usage = SimpleNamespace(prompt_tokens=1, completion_tokens=1, total_tokens=2)
    bad_response = SimpleNamespace(choices=[bad_choice], usage=bad_usage)

    class _BadCompletions:
        def create(self, *args, **kwargs):
            return bad_response

    class _BadChat:
        completions = _BadCompletions()

    class _BadClient:
        chat = _BadChat()

    engine.client = _BadClient()  # type: ignore[assignment]
    out = engine._decide_with_llm(
        _base_scout(),
        _base_review(),
        assumption_risks=[],
        trigger_reason="Malformed JSON check",
        avg_score=6.25,
        final_recommendation="MONITOR",
    )
    assert out.get("decision") == "MAYBE"
    assert "average score" in (out.get("rationale") or "").lower()


def test_invalid_model_decision_falls_back_to_safe_maybe():
    engine = PartnerDecisionEngine(use_llm_fallback=True, api_key="fake-key")
    invalid_message = SimpleNamespace(content='{"decision":"HOLD","reasoning":"x","confidence":0.7}')
    invalid_choice = SimpleNamespace(message=invalid_message, finish_reason="stop")
    invalid_usage = SimpleNamespace(prompt_tokens=1, completion_tokens=1, total_tokens=2)
    invalid_response = SimpleNamespace(choices=[invalid_choice], usage=invalid_usage)

    class _InvalidCompletions:
        def create(self, *args, **kwargs):
            return invalid_response

    class _InvalidChat:
        completions = _InvalidCompletions()

    class _InvalidClient:
        chat = _InvalidChat()

    engine.client = _InvalidClient()  # type: ignore[assignment]
    out = engine._decide_with_llm(
        _base_scout(),
        _base_review(),
        assumption_risks=[],
        trigger_reason="Invalid decision check",
        avg_score=6.25,
        final_recommendation="MONITOR",
    )
    assert out.get("decision") == "MAYBE"


def test_strong_verdict_below_yes_bar_is_maybe_not_no():
    engine = PartnerDecisionEngine(use_llm_fallback=False, api_key=None)
    review = _base_review()
    review["verdict"] = "STRONG"
    review.update(
        {
            "market_score": 7,
            "product_score": 8,
            "technical_score": 7,
            "execution_score": 7,
        }
    )  # avg = 7.25
    out = engine.decide(_base_scout(), review)
    assert out.get("decision") == "MAYBE"
    rl = (out.get("rationale") or "").lower()
    assert "we monitor at this stage" in rl
    assert "strong-yes bar" in rl or "grey zone" in rl


def test_scout_biggest_unknown_alone_does_not_trigger_llm_escalation():
    engine = PartnerDecisionEngine(use_llm_fallback=True, api_key=None)
    # Disable grey-zone deep dive so the test only validates the biggest_unknown behaviour,
    # not the new grey-zone trigger (avg_score=7.0 would otherwise sit inside [6.5, 7.5]).
    engine._rules.setdefault("llm_fallback_triggers", {})["grey_zone_deep_dive"] = False
    scout = {**_base_scout(), "biggest_unknown": "Enterprise sales cycle length unproven"}
    review = _base_review()
    review.update(
        {
            "market_score": 7,
            "product_score": 7,
            "technical_score": 7,
            "execution_score": 7,
            "assumption_feedback": [],
        }
    )

    def _should_not_call_llm(*args, **kwargs):
        raise AssertionError("LLM fallback should not run when only scout biggest_unknown is present")

    engine._decide_with_llm = _should_not_call_llm  # type: ignore[method-assign]
    out = engine.decide(scout, review)
    assert out.get("decision") == "MAYBE"
    assert "Biggest unknown" in " ".join(out.get("assumption_risks") or [])


def test_llm_stats_counter_increments_on_failures():
    engine = PartnerDecisionEngine(use_llm_fallback=True, api_key="fake-key")

    class _BoomCompletions:
        def create(self, *args, **kwargs):
            raise RuntimeError("boom")

    class _BoomChat:
        completions = _BoomCompletions()

    class _BoomClient:
        chat = _BoomChat()

    engine.client = _BoomClient()  # type: ignore[assignment]
    engine._decide_with_llm(
        _base_scout(),
        _base_review(),
        assumption_risks=[],
        trigger_reason="Stats check",
        avg_score=6.25,
        final_recommendation="MONITOR",
    )
    assert engine._llm_stats.get("fallback_invocations", 0) >= 1
    assert engine._llm_stats.get("request_errors", 0) >= 1
