"""Sub-project 4, Phase B: bounded evidence retrieval against a plan."""

from unittest.mock import patch

import pytest

from evidence.models import EvidencePlanRecord, TrustClass, VerificationState
from evidence.retrieval import MAX_QUERIES, execute_evidence_plan


def _plan(**overrides):
    defaults = dict(
        user_id="user_test",
        opportunity_id="opp-1",
        trigger_type="dispatch",
        missing_evidence=["market", "product", "technical", "execution"],
        search_questions=[
            "What is the total addressable market?",
            "What is the product's value proposition?",
            "How complex is the technology?",
            "What is the growth velocity?",
        ],
        max_artifacts=5,
        budget_usd=0,
        plan_hash="hash-1",
    )
    defaults.update(overrides)
    return EvidencePlanRecord(**defaults)


class _FakeEvidenceRepository:
    def __init__(self):
        self.ingested: list = []

    async def ingest_artifact(self, artifact, *, items=()):
        self.ingested.append((artifact, list(items)))
        return artifact, list(items)


@pytest.mark.asyncio
async def test_sources_found_are_ingested_with_attribution():
    repo = _FakeEvidenceRepository()
    plan = _plan()
    pack = {
        "provider": "exa",
        "sources": [
            {"title": "Market report", "url": "https://example.com/market", "snippet": "TAM is $10B."},
            {"title": "No snippet", "url": "https://example.com/empty", "snippet": ""},
        ],
    }

    with patch("evidence.retrieval.retrieve_source_pack_merged", return_value=pack) as mock_retrieve:
        result = await execute_evidence_plan(
            user_id="user_test", company_id="company-1", opportunity_id="opp-1",
            plan=plan, evidence_repository=repo, company_name="Acme",
        )

    assert result["artifacts_ingested"] == 1  # the empty-snippet source is skipped
    assert len(repo.ingested) == 1
    artifact, items = repo.ingested[0]
    assert artifact.retrieval_provider == "exa"
    assert artifact.retrieval_query.startswith("Acme ")
    assert items[0].display_excerpt == "TAM is $10B."
    # Called via asyncio.to_thread, but the underlying function still got the right kwargs.
    mock_retrieve.assert_called_once()
    _, kwargs = mock_retrieve.call_args
    assert kwargs["max_total_sources"] == plan.max_artifacts


@pytest.mark.asyncio
async def test_no_sources_ingests_nothing_and_does_not_error():
    repo = _FakeEvidenceRepository()
    plan = _plan()

    with patch("evidence.retrieval.retrieve_source_pack_merged", return_value={"provider": "exa", "sources": []}):
        result = await execute_evidence_plan(
            user_id="user_test", company_id="company-1", opportunity_id="opp-1",
            plan=plan, evidence_repository=repo, company_name="Acme",
        )

    assert result == {"artifacts_ingested": 0, "queries_run": len(plan.search_questions[:MAX_QUERIES])}
    assert repo.ingested == []


@pytest.mark.asyncio
async def test_queries_are_capped_regardless_of_a_longer_plan():
    repo = _FakeEvidenceRepository()
    plan = _plan(search_questions=[f"question {i}" for i in range(10)])

    with patch("evidence.retrieval.retrieve_source_pack_merged", return_value={"provider": "exa", "sources": []}) as mock_retrieve:
        await execute_evidence_plan(
            user_id="user_test", company_id="company-1", opportunity_id="opp-1",
            plan=plan, evidence_repository=repo, company_name="Acme",
        )

    _, kwargs = mock_retrieve.call_args
    assert len(kwargs["queries"]) == MAX_QUERIES


@pytest.mark.asyncio
async def test_companys_own_domain_is_official_and_verified_unconditionally():
    repo = _FakeEvidenceRepository()
    plan = _plan()
    pack = {
        "provider": "exa",
        "sources": [
            {"title": "Acme homepage", "url": "https://www.acme.com/product", "snippet": "Acme builds widgets."},
        ],
    }

    with patch("evidence.retrieval.retrieve_source_pack_merged", return_value=pack):
        await execute_evidence_plan(
            user_id="user_test", company_id="company-1", opportunity_id="opp-1",
            plan=plan, evidence_repository=repo, company_name="Acme",
            company_website="https://acme.com",
        )

    artifact, items = repo.ingested[0]
    assert artifact.trust_class == TrustClass.OFFICIAL
    assert items[0].verification_state == VerificationState.VERIFIED


@pytest.mark.asyncio
async def test_single_independent_source_stays_unverified():
    """No corroboration, not the company's own domain -- must not be
    upgraded to verified just because it was retrieved."""
    repo = _FakeEvidenceRepository()
    plan = _plan()
    pack = {
        "provider": "exa",
        "sources": [
            {"title": "A blog post", "url": "https://someblog.com/post", "snippet": "Acme raised a round."},
        ],
    }

    with patch("evidence.retrieval.retrieve_source_pack_merged", return_value=pack):
        await execute_evidence_plan(
            user_id="user_test", company_id="company-1", opportunity_id="opp-1",
            plan=plan, evidence_repository=repo, company_name="Acme",
            company_website="https://acme.com",
        )

    artifact, items = repo.ingested[0]
    assert artifact.trust_class == TrustClass.INDEPENDENT
    assert items[0].verification_state == VerificationState.UNVERIFIED


@pytest.mark.asyncio
async def test_two_independent_domains_corroborate_each_other():
    repo = _FakeEvidenceRepository()
    plan = _plan()
    pack = {
        "provider": "exa",
        "sources": [
            {"title": "News A", "url": "https://techcrunch.com/acme", "snippet": "Acme raised $10M."},
            {"title": "News B", "url": "https://reuters.com/acme", "snippet": "Acme closed a $10M round."},
        ],
    }

    with patch("evidence.retrieval.retrieve_source_pack_merged", return_value=pack):
        await execute_evidence_plan(
            user_id="user_test", company_id="company-1", opportunity_id="opp-1",
            plan=plan, evidence_repository=repo, company_name="Acme",
            company_website="https://acme.com",
        )

    assert len(repo.ingested) == 2
    for artifact, items in repo.ingested:
        assert artifact.trust_class == TrustClass.INDEPENDENT
        assert items[0].verification_state == VerificationState.VERIFIED


@pytest.mark.asyncio
async def test_two_sources_from_the_same_domain_do_not_corroborate():
    """Corroboration requires distinct domains -- two pages from the same
    site are one source repeated, not independent confirmation."""
    repo = _FakeEvidenceRepository()
    plan = _plan()
    pack = {
        "provider": "exa",
        "sources": [
            {"title": "Page A", "url": "https://someblog.com/a", "snippet": "Acme is great."},
            {"title": "Page B", "url": "https://someblog.com/b", "snippet": "More about Acme."},
        ],
    }

    with patch("evidence.retrieval.retrieve_source_pack_merged", return_value=pack):
        await execute_evidence_plan(
            user_id="user_test", company_id="company-1", opportunity_id="opp-1",
            plan=plan, evidence_repository=repo, company_name="Acme",
            company_website="https://acme.com",
        )

    for artifact, items in repo.ingested:
        assert items[0].verification_state == VerificationState.UNVERIFIED


@pytest.mark.asyncio
async def test_bare_domain_company_website_still_matches_official():
    """ScoutInfo.lookup_website is stored without a scheme ("stripe.com",
    not "https://stripe.com") -- confirmed against real production data.
    urlparse("stripe.com").netloc is empty (parsed as a relative path, not
    a host), which silently broke every official-domain match until fixed."""
    repo = _FakeEvidenceRepository()
    plan = _plan()
    pack = {
        "provider": "exa",
        "sources": [
            {"title": "Stripe homepage", "url": "https://stripe.com/", "snippet": "Payments infrastructure."},
        ],
    }

    with patch("evidence.retrieval.retrieve_source_pack_merged", return_value=pack):
        await execute_evidence_plan(
            user_id="user_test", company_id="company-1", opportunity_id="opp-1",
            plan=plan, evidence_repository=repo, company_name="Stripe",
            company_website="stripe.com",
        )

    artifact, items = repo.ingested[0]
    assert artifact.trust_class == TrustClass.OFFICIAL
    assert items[0].verification_state == VerificationState.VERIFIED


@pytest.mark.asyncio
async def test_no_company_website_never_marks_anything_official():
    repo = _FakeEvidenceRepository()
    plan = _plan()
    pack = {
        "provider": "exa",
        "sources": [
            {"title": "Some page", "url": "https://example.com/a", "snippet": "Content."},
        ],
    }

    with patch("evidence.retrieval.retrieve_source_pack_merged", return_value=pack):
        await execute_evidence_plan(
            user_id="user_test", company_id="company-1", opportunity_id="opp-1",
            plan=plan, evidence_repository=repo, company_name="Acme",
            company_website=None,
        )

    artifact, _ = repo.ingested[0]
    assert artifact.trust_class == TrustClass.INDEPENDENT


@pytest.mark.asyncio
async def test_empty_plan_skips_retrieval_entirely():
    repo = _FakeEvidenceRepository()
    plan = _plan(missing_evidence=[], search_questions=[])

    with patch("evidence.retrieval.retrieve_source_pack_merged") as mock_retrieve:
        result = await execute_evidence_plan(
            user_id="user_test", company_id="company-1", opportunity_id="opp-1",
            plan=plan, evidence_repository=repo, company_name="Acme",
        )

    mock_retrieve.assert_not_called()
    assert result == {"artifacts_ingested": 0, "queries_run": 0}
