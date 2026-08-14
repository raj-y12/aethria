from contradiction_gate import apply_contradiction_gate


def _packet(claim_type, *, excerpt="Verified evidence", relationship="supports", verification="verified", access="public", user_id="fund-a"):
    return {
        "current_supported_claims": [{"claim_id": "c-1", "claim_type": claim_type, "display_text": excerpt}],
        "materially_contradicted_claims": [],
        "evidence": [{"user_id": user_id, "claim_id": "c-1", "relationship": relationship, "display_excerpt": excerpt, "source_locator": "source.example", "verification_state": verification, "access_class": access}],
    }


def test_verified_operation_downgrades_execution_impossible_and_preserves_original():
    result = apply_contradiction_gate(
        user_id="fund-a",
        review={"execution_reasoning": ["Execution is impossible."]},
        canonical_context={"contexts": {"regulatory": _packet("operational_feasibility", excerpt="Verified current commercial operation.")}},
    )
    assert result["correction_count"] == 1
    assert result["corrections"][0]["state"] == "directly_contradicted"
    assert result["original_review"]["execution_reasoning"] == ["Execution is impossible."]
    assert "Execution is impossible" not in result["guarded_review"]["execution_reasoning"][0]


def test_supported_canonical_domains_guard_founder_traction_funding_and_product():
    review = {
        "team_analysis": ["Founder has no relevant operating experience."],
        "execution_weaknesses": ["No traction or revenue."],
        "key_risks": ["Unfunded / no funding history."],
        "product_weaknesses": ["Product is technically infeasible."],
    }
    contexts = {
        "founder": _packet("founder_operating_history"),
        "traction": _packet("traction_revenue"),
        "funding": _packet("funding_stage"),
        "product": _packet("product_capability", excerpt="Deployed operational product."),
    }
    result = apply_contradiction_gate(user_id="fund-a", review=review, canonical_context={"contexts": contexts})
    assert result["correction_count"] == 4
    assert {row["criterion"] for row in result["corrections"]} == {"founder", "traction", "funding", "product"}


def test_unsupported_judgment_becomes_uncertain_only_when_canonical_coverage_is_unverified():
    result = apply_contradiction_gate(
        user_id="fund-a",
        review={"product_reasoning": ["Product is technically infeasible."]},
        canonical_context={"contexts": {"product": _packet("product_capability", verification="unverified")}},
    )
    assert result["corrections"][0]["state"] == "uncertain"
    assert result["guarded_review"]["product_reasoning"][0].startswith("Uncertain")


def test_conflicting_canonical_evidence_is_exposed_as_unresolved():
    packet = _packet("traction_revenue")
    packet["materially_contradicted_claims"] = [{"claim_id": "c-1", "claim_type": "traction_revenue"}]
    result = apply_contradiction_gate(
        user_id="fund-a",
        review={"execution_reasoning": ["No traction."]},
        canonical_context={"contexts": {"traction": packet}},
    )
    assert result["corrections"][0]["state"] == "conflict"
    assert "Evidence conflict / unresolved" in result["guarded_review"]["execution_reasoning"][0]


def test_partial_canonical_support_is_reported_as_partial_contradiction():
    result = apply_contradiction_gate(
        user_id="fund-a",
        review={"product_reasoning": ["Product is technically infeasible."]},
        canonical_context={"contexts": {"product": _packet("product_capability", relationship="partially_establishes")}},
    )
    assert result["corrections"][0]["state"] == "partially_contradicted"
    assert result["criterion_states"]["competition"] == "not_applicable"


def test_tenant_and_private_evidence_fail_closed_and_legacy_domains_are_untouched():
    private_packet = _packet("market_size", access="tenant_private")
    result = apply_contradiction_gate(
        user_id="fund-a",
        review={"market_weaknesses": ["No traction."]},
        canonical_context={"contexts": {"market": private_packet}},
    )
    assert result["correction_count"] == 0

    try:
        apply_contradiction_gate(
            user_id="fund-a",
            review={"team_analysis": ["Founder has no relevant operating experience."]},
            canonical_context={"contexts": {"founder": _packet("founder_operating_history", user_id="fund-b")}},
        )
    except ValueError as exc:
        assert "tenant" in str(exc)
    else:
        raise AssertionError("cross-tenant evidence must fail closed")

    untouched = apply_contradiction_gate(
        user_id="fund-a",
        review={"competition_analysis": ["No credible competition."]},
        canonical_context={"contexts": {}},
    )
    assert untouched["correction_count"] == 0


def test_historical_evaluation_snapshot_is_not_mutated():
    review = {
        "execution_reasoning": ["Execution is impossible."],
        "reviews": [{"reviewer_type": "DefaultReviewer", "execution_reasoning": ["Execution is impossible."]}],
    }
    result = apply_contradiction_gate(
        user_id="fund-a",
        review=review,
        canonical_context={"contexts": {"regulatory": _packet("operational_feasibility")}},
    )
    assert result["original_review"]["reviews"] == review["reviews"]
    assert result["guarded_review"]["reviews"] == review["reviews"]


def test_partner_rationale_fields_are_guardable_with_same_gate():
    result = apply_contradiction_gate(
        user_id="fund-a",
        review={"decision_rationale": "Execution is impossible."},
        canonical_context={"contexts": {"regulatory": _packet("operational_feasibility")}},
    )
    assert "Execution is impossible" not in result["guarded_review"]["decision_rationale"]


def test_canonical_competitor_evidence_guards_no_competition_claim():
    result = apply_contradiction_gate(
        user_id="fund-a",
        review={"competition_analysis": ["No credible competition exists."]},
        canonical_context={"contexts": {"competition": _packet("competitor_existence", excerpt="The company competes with Stripe.")}},
    )
    assert result["correction_count"] == 1
    assert result["corrections"][0]["criterion"] == "competition"
    assert result["corrections"][0]["state"] == "directly_contradicted"
    assert "No credible competition" not in result["guarded_review"]["competition_analysis"][0]


def test_generic_competitive_judgment_is_not_a_competition_contradiction():
    result = apply_contradiction_gate(
        user_id="fund-a",
        review={"competition_analysis": ["Competition is intense and crowded."]},
        canonical_context={"contexts": {"competition": _packet("competitor_existence", excerpt="The company competes with Stripe.")}},
    )
    assert result["correction_count"] == 0


def test_verified_subscription_revenue_guards_no_recurring_revenue_claim():
    result = apply_contradiction_gate(
        user_id="fund-a",
        review={"business_model_analysis": ["The company has no recurring revenue."]},
        canonical_context={"contexts": {"commercial": _packet("revenue_model", excerpt="The company sells a recurring subscription.")}},
    )
    assert result["correction_count"] == 1
    assert result["corrections"][0]["criterion"] == "commercial"


def test_unattractive_economics_remains_reviewer_judgment():
    result = apply_contradiction_gate(
        user_id="fund-a",
        review={"business_model_analysis": ["The economics are unattractive."]},
        canonical_context={"contexts": {"commercial": _packet("gross_margin", excerpt="Gross margin is 72%.")}},
    )
    assert result["correction_count"] == 0
