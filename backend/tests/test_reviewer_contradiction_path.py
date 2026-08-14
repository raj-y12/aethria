from reviewer.engine import ReviewerEngine


def test_reviewer_runtime_guard_returns_guarded_primary_output():
    engine = ReviewerEngine.__new__(ReviewerEngine)
    engine.tenant_user_id = "fund-a"
    guarded, audit = engine._guard_review_output(
        {"business_model_analysis": ["The company has no recurring revenue."]},
        {"contexts": {"commercial": {
            "current_supported_claims": [{"claim_type": "revenue_model", "display_text": "Recurring subscription revenue."}],
            "evidence": [{"user_id": "fund-a", "relationship": "supports", "verification_state": "verified", "source_locator": "source.example", "display_excerpt": "Recurring subscription revenue."}],
        }}},
    )
    assert "no recurring revenue" not in guarded["business_model_analysis"][0].lower()
    assert audit["correction_count"] == 1
