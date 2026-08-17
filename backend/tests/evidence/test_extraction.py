"""Sub-project 4, Phase C: LLM-based extraction of claims from evidence."""

import json

import pytest

from evaluation_v2.models import CriterionRule, DecisionSafetyPolicy, EvaluationPolicy, EvidenceEligibilityPolicy
from evidence.extraction import extract_claims_from_evidence


def _policy():
    return EvaluationPolicy(
        policy_version_id="policy-v1",
        policy_hash="policy-hash-v1",
        rubric_version="rubric-v1",
        partner_rules_version="rules-v1",
        partner_rules_hash="rules-hash-v1",
        criteria=[
            CriterionRule(criterion="market", claim_types=["tam", "growth_rate"], weight=0.6),
            CriterionRule(criterion="product", claim_types=["value_prop"], weight=0.4),
        ],
        advance_threshold=7.2,
        pass_threshold=4.0,
        advance_comparison="greater_than_or_equal",
        pass_comparison="less_than",
        minimum_scored_weight=0.5,
        decision_safety=DecisionSafetyPolicy(
            evidence_eligibility=EvidenceEligibilityPolicy(
                allowed_assertion_classes=["externally_verified"],
                allowed_relationships=["supports", "partially_establishes"],
                require_verified_evidence=True,
                min_support_strength=0.5,
                min_source_quality=0.4,
                blocked_trust_classes=["model", "unknown"],
            ),
            critical_risk_claim_types=["critical_risk"],
            hard_exclusion_claim_types=["excluded_sector"],
            claim_confidence={
                "minimum_eligible": 0.5, "full_confidence_at": 0.8,
                "score_cap_below_full_confidence": 7.19,
                "recommendation_confidence_cap_below_full_confidence": 0.6,
                "zero_confidence_ineligible": True,
            },
            freshness={
                "max_age_days": 180, "expired_action": "ineligible", "undated_action": "ineligible",
                "future_dated_action": "ineligible", "stale_action": "cap",
                "stale_score_cap": 7.19, "stale_confidence_cap": 0.6,
            },
            source_quality={
                "full_confidence_at": 0.8, "score_cap_below_full_quality": 7.19,
                "recommendation_confidence_cap_below_full_quality": 0.65,
            },
        ),
        hard_exclusion_claim_types=["excluded_sector"],
    )


def _rubric():
    return {
        "dimensions": [
            {
                "id": "market_score", "name": "Market", "question": "Is this market worth winning?",
                "definition": "Market size, growth, timing.",
                "high": {"range": [8, 10], "criteria": "Large, growing, well-timed."},
                "mid": {"range": [5, 7], "criteria": "Moderate market."},
                "low": {"range": [1, 4], "criteria": "Small or stagnant."},
            },
            {
                "id": "product_score", "name": "Product", "question": "Does this solve a real problem?",
                "definition": "Problem-solution fit.",
                "high": {"range": [8, 10], "criteria": "Clear fit."},
                "mid": {"range": [5, 7], "criteria": "Reasonable fit."},
                "low": {"range": [1, 4], "criteria": "Unclear fit."},
            },
        ],
    }


def _items():
    return [
        {"evidence_item_id": "item-1", "display_excerpt": "TAM is estimated at $10B and growing 20% YoY."},
        {"evidence_item_id": "item-2", "display_excerpt": "Customers report the product saves them 5 hours a week."},
    ]


class _FakeEvidenceRepository:
    def __init__(self):
        self.claims: list = []

    async def create_claim(self, claim, *, links, created_by):
        self.claims.append((claim, list(links), created_by))
        return {"claim_id": f"claim-{len(self.claims)}"}


class _FakeMessage:
    def __init__(self, content):
        self.content = content


class _FakeChoice:
    def __init__(self, content):
        self.message = _FakeMessage(content)


class _FakeResponse:
    def __init__(self, content):
        self.choices = [_FakeChoice(content)] if content is not None else []


def _fake_client(responses):
    """responses: list of JSON-serializable payloads (or None for empty), one per call."""
    calls = {"n": 0}

    class _Completions:
        def create(self, **kwargs):
            i = calls["n"]
            calls["n"] += 1
            payload = responses[i] if i < len(responses) else {"claims": []}
            content = None if payload is None else json.dumps(payload)
            return _FakeResponse(content)

    class _Chat:
        completions = _Completions()

    class _Client:
        chat = _Chat()

    return _Client(), calls


@pytest.mark.asyncio
async def test_valid_extraction_creates_grounded_scored_claims(monkeypatch):
    repo = _FakeEvidenceRepository()
    client, calls = _fake_client([
        {"claims": [{
            "claim_type": "tam", "criterion_score": 7.5, "confidence": 0.8,
            "display_text": "TAM is $10B, growing 20% YoY.",
            "supporting_evidence_item_ids": ["item-1"],
        }]},
        {"claims": []},
    ])
    monkeypatch.setattr("evidence.extraction.build_openai_client", lambda api_key: client)

    result = await extract_claims_from_evidence(
        user_id="user_test", company_id="company-1", opportunity_id="opp-1",
        missing_evidence=["market", "product"], evidence_items=_items(),
        rubric=_rubric(), policy=_policy(), evidence_repository=repo,
        api_key="test-key", model="gpt-5-nano",
    )

    assert result == {"claims_created": 1, "dimensions_attempted": 2}
    claim, links, created_by = repo.claims[0]
    assert claim.claim_type == "tam"
    assert claim.normalized_value == {"criterion_score": 7.5}
    assert claim.confidence == 0.8
    assert len(links) == 1
    assert links[0].evidence_item_id == "item-1"
    assert created_by == "user_test"


@pytest.mark.asyncio
async def test_score_band_and_justification_are_captured_when_the_model_provides_them(monkeypatch):
    repo = _FakeEvidenceRepository()
    client, _ = _fake_client([
        {"claims": [{
            "claim_type": "tam", "criterion_score": 8.5, "confidence": 0.8,
            "score_band": "high", "score_justification": "Meets the high-band $3B+ TAM criterion; "
                "not a 10 because growth rate is unquantified.",
            "display_text": "TAM is $10B, growing 20% YoY.",
            "supporting_evidence_item_ids": ["item-1"],
        }]},
    ])
    monkeypatch.setattr("evidence.extraction.build_openai_client", lambda api_key: client)

    await extract_claims_from_evidence(
        user_id="user_test", company_id="company-1", opportunity_id="opp-1",
        missing_evidence=["market"], evidence_items=_items(),
        rubric=_rubric(), policy=_policy(), evidence_repository=repo,
        api_key="test-key", model="gpt-5-nano",
    )

    claim, _, _ = repo.claims[0]
    assert claim.normalized_value["score_band"] == "high"
    assert "high-band" in claim.normalized_value["score_justification"]


@pytest.mark.asyncio
async def test_invalid_score_band_from_the_model_is_dropped_not_stored(monkeypatch):
    repo = _FakeEvidenceRepository()
    client, _ = _fake_client([
        {"claims": [{
            "claim_type": "tam", "criterion_score": 8.5, "confidence": 0.8,
            "score_band": "extremely high", "score_justification": "  ",
            "display_text": "TAM is $10B, growing 20% YoY.",
            "supporting_evidence_item_ids": ["item-1"],
        }]},
    ])
    monkeypatch.setattr("evidence.extraction.build_openai_client", lambda api_key: client)

    await extract_claims_from_evidence(
        user_id="user_test", company_id="company-1", opportunity_id="opp-1",
        missing_evidence=["market"], evidence_items=_items(),
        rubric=_rubric(), policy=_policy(), evidence_repository=repo,
        api_key="test-key", model="gpt-5-nano",
    )

    claim, _, _ = repo.claims[0]
    assert claim.normalized_value == {"criterion_score": 8.5}


@pytest.mark.asyncio
async def test_claim_with_no_valid_supporting_evidence_is_dropped(monkeypatch):
    repo = _FakeEvidenceRepository()
    client, _ = _fake_client([
        {"claims": [{
            "claim_type": "tam", "criterion_score": 8, "confidence": 0.9,
            "display_text": "Fabricated claim.",
            "supporting_evidence_item_ids": ["item-does-not-exist"],
        }]},
    ])
    monkeypatch.setattr("evidence.extraction.build_openai_client", lambda api_key: client)

    result = await extract_claims_from_evidence(
        user_id="user_test", company_id="company-1", opportunity_id="opp-1",
        missing_evidence=["market"], evidence_items=_items(),
        rubric=_rubric(), policy=_policy(), evidence_repository=repo,
        api_key="test-key", model="gpt-5-nano",
    )

    assert result["claims_created"] == 0
    assert repo.claims == []


@pytest.mark.asyncio
async def test_claim_type_outside_dimensions_accepted_list_is_dropped(monkeypatch):
    repo = _FakeEvidenceRepository()
    client, _ = _fake_client([
        {"claims": [{
            "claim_type": "invented_type", "criterion_score": 8, "confidence": 0.9,
            "display_text": "Off-schema claim.",
            "supporting_evidence_item_ids": ["item-1"],
        }]},
    ])
    monkeypatch.setattr("evidence.extraction.build_openai_client", lambda api_key: client)

    result = await extract_claims_from_evidence(
        user_id="user_test", company_id="company-1", opportunity_id="opp-1",
        missing_evidence=["market"], evidence_items=_items(),
        rubric=_rubric(), policy=_policy(), evidence_repository=repo,
        api_key="test-key", model="gpt-5-nano",
    )

    assert result["claims_created"] == 0


@pytest.mark.asyncio
async def test_empty_claims_response_is_not_an_error(monkeypatch):
    repo = _FakeEvidenceRepository()
    client, _ = _fake_client([{"claims": []}])
    monkeypatch.setattr("evidence.extraction.build_openai_client", lambda api_key: client)

    result = await extract_claims_from_evidence(
        user_id="user_test", company_id="company-1", opportunity_id="opp-1",
        missing_evidence=["market"], evidence_items=_items(),
        rubric=_rubric(), policy=_policy(), evidence_repository=repo,
        api_key="test-key", model="gpt-5-nano",
    )

    assert result == {"claims_created": 0, "dimensions_attempted": 1}


@pytest.mark.asyncio
async def test_empty_content_retries_once_with_a_larger_budget(monkeypatch):
    repo = _FakeEvidenceRepository()
    client, calls = _fake_client([
        None,  # first attempt: empty content (reasoning-token exhaustion)
        {"claims": []},  # retry succeeds
    ])
    monkeypatch.setattr("evidence.extraction.build_openai_client", lambda api_key: client)

    await extract_claims_from_evidence(
        user_id="user_test", company_id="company-1", opportunity_id="opp-1",
        missing_evidence=["market"], evidence_items=_items(),
        rubric=_rubric(), policy=_policy(), evidence_repository=repo,
        api_key="test-key", model="gpt-5-nano",
    )

    assert calls["n"] == 2


@pytest.mark.asyncio
async def test_no_missing_evidence_skips_extraction_entirely(monkeypatch):
    repo = _FakeEvidenceRepository()
    called = []
    monkeypatch.setattr("evidence.extraction.build_openai_client", lambda api_key: called.append(1))

    result = await extract_claims_from_evidence(
        user_id="user_test", company_id="company-1", opportunity_id="opp-1",
        missing_evidence=[], evidence_items=_items(),
        rubric=_rubric(), policy=_policy(), evidence_repository=repo,
        api_key="test-key", model="gpt-5-nano",
    )

    assert not called
    assert result == {"claims_created": 0, "dimensions_attempted": 0}


@pytest.mark.asyncio
async def test_no_evidence_items_skips_extraction_entirely(monkeypatch):
    repo = _FakeEvidenceRepository()
    called = []
    monkeypatch.setattr("evidence.extraction.build_openai_client", lambda api_key: called.append(1))

    result = await extract_claims_from_evidence(
        user_id="user_test", company_id="company-1", opportunity_id="opp-1",
        missing_evidence=["market"], evidence_items=[],
        rubric=_rubric(), policy=_policy(), evidence_repository=repo,
        api_key="test-key", model="gpt-5-nano",
    )

    assert not called
    assert result == {"claims_created": 0, "dimensions_attempted": 0}
