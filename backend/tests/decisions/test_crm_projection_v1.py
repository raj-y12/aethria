import pytest

from decisions.crm_projection import build_crm_projection_v1


def _projection(**overrides):
    data = {
        "user_id": "user-1",
        "company": {"company_id": "company-1", "canonical_name": "Acme", "canonical_domain": "acme.ai", "sector": "climate", "geography": "IE"},
        "opportunity": {"opportunity_id": "opp-1", "workflow_state": "monitoring", "updated_at": "2026-08-12T10:00:00Z"},
        "recommendation": {"recommendation_id": "rec-1", "recommended_state": "monitor", "confidence": 0.7, "decision_drivers": ["Retention"], "principal_risks": ["Regulatory uncertainty"]},
        "ruling": {"ruling_id": "rul-1", "decision": "invest", "rationale": "Proceed", "created_at": "2026-08-12T09:00:00Z"},
        "evaluation": {"evaluation_id": "eval-1", "completed_at": "2026-08-12T08:00:00Z"},
        "founders": [{"person_id": "person-1", "name": "Jane Smith", "current_role": "Founder & CEO", "relevant_prior_experience": ["OldCo"]}],
        "memo": {"memo_id": "memo-1", "url": "https://aethria.example/memos/opp-1"},
        "provenance": [{"source_url": "https://acme.ai", "source_type": "official_site"}],
    }
    data.update(overrides)
    return build_crm_projection_v1(**data)


def test_projection_is_versioned_and_uses_canonical_ids():
    projection = _projection()
    assert projection["schema_version"] == "crm_projection_v1"
    assert projection["company"]["aethria_company_id"] == "company-1"
    assert projection["opportunity"]["aethria_opportunity_id"] == "opp-1"
    assert projection["founders"][0]["person_id"] == "person-1"


def test_projection_preserves_recommendation_and_human_ruling_separately():
    projection = _projection()
    assert projection["recommendation"]["state"] == "MONITOR"
    assert projection["human_ruling"]["decision"] == "INVEST"


def test_projection_keeps_unresolved_founder_identity_explicit():
    projection = _projection(founders=[{"name": "Unknown Founder", "identity_status": "unresolved"}])
    assert projection["founders"] == [{"person_id": None, "name": "Unknown Founder", "current_role": None, "relevant_prior_experience": [], "identity_status": "unresolved"}]


def test_projection_is_stable_and_excludes_raw_internal_structures():
    left = _projection()
    right = _projection()
    assert left == right
    assert "agent_trace" not in left
    assert "claim_ledger" not in left
    assert "rationale" not in left["human_ruling"]


def test_projection_requires_explicit_tenant():
    with pytest.raises(RuntimeError):
        _projection(user_id="")
