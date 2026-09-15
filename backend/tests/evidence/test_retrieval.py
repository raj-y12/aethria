"""Sub-project 4, Phase B: bounded evidence retrieval against a plan."""

from itertools import count
from unittest.mock import patch

import pytest

from evidence.models import EvidenceItemRecord, EvidencePlanRecord, TrustClass, VerificationState
from evidence.retrieval import MAX_QUERIES, analytical_excerpt, execute_evidence_plan


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


def test_analytical_excerpt_preserves_signal_after_long_consent_boilerplate():
    content = "Cookie settings and privacy choices. " * 100 + " Trusted by We Are Riley and Mango Media."
    excerpt = analytical_excerpt(content)
    assert len(excerpt) <= 2000
    assert "Trusted by We Are Riley and Mango Media" in excerpt


def test_analytical_excerpt_preserves_middle_customer_signal_and_reviewer_attribution():
    content = "Cookie settings and privacy choices. " * 70
    content += " Trusted by We Are Riley and Mango Media; customer logos are company-reported, not independently verified. "
    content += " Footer privacy settings and consent management. " * 70
    excerpt = analytical_excerpt(content)
    assert "We Are Riley" in excerpt and "Mango Media" in excerpt
    from investment_analysis.grounding import reviewer_evidence
    packet, _, _ = reviewer_evidence([{
        "claim_id": "customers", "claim_type": "customer_signal",
        "display_text": excerpt, "evidence_relationships": [{
            "evidence_item_id": "item", "artifact_id": "source", "source_uri": "https://glitchads.ai",
            "display_excerpt": excerpt, "verification_state": "verified", "source_quality": 1.0,
        }], "supporting_evidence_ids": ["item"],
    }], company_name="Glitch Ads", company_website="glitchads.ai")
    assert "company-reported" in packet[0]["statement"]
    assert "independently verified" in packet[0]["statement"]


class _FakeEvidenceRepository:
    def __init__(self):
        self.ingested: list = []
        self._ids = count(1)

    async def ingest_artifact(self, artifact, *, items=()):
        # Mirror the real repository: an EvidenceItemInput becomes an
        # EvidenceItemRecord (gains an evidence_item_id) only once "stored".
        stored_items = [
            EvidenceItemRecord(**item.model_dump(), artifact_id=f"artifact-{next(self._ids)}")
            for item in items
        ]
        self.ingested.append((artifact, stored_items))
        return artifact, stored_items


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
    # One call per query now (audit HIGH-B4), not one batched call across all
    # of them -- the mock returns the same pack every time, so later calls'
    # sources are recognized as duplicates and deduped, not double-ingested.
    assert mock_retrieve.call_count == len(plan.search_questions)
    _, kwargs = mock_retrieve.call_args
    assert kwargs["max_total_sources"] == 4


@pytest.mark.asyncio
async def test_no_sources_ingests_nothing_and_does_not_error():
    repo = _FakeEvidenceRepository()
    plan = _plan()

    with patch("evidence.retrieval.retrieve_source_pack_merged", return_value={"provider": "exa", "sources": []}):
        result = await execute_evidence_plan(
            user_id="user_test", company_id="company-1", opportunity_id="opp-1",
            plan=plan, evidence_repository=repo, company_name="Acme",
        )

    assert result == {
        "artifacts_ingested": 0,
        "queries_run": len(plan.search_questions[:MAX_QUERIES]),
        "verified_items": [],
    }
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

    # One retrieval call per query now (audit HIGH-B4), not one batched call
    # with all queries -- capping still means MAX_QUERIES calls, not more.
    assert mock_retrieve.call_count == MAX_QUERIES
    for call in mock_retrieve.call_args_list:
        assert len(call.kwargs["queries"]) == 1


@pytest.mark.asyncio
async def test_every_rubric_dimension_gets_a_dedicated_query():
    """Regression (audit CRITICAL-2): MAX_QUERIES used to be 3, silently
    dropping targeted retrieval for the 4th/5th missing dimension on a real
    plan (the rubric has exactly 5 dimensions -- market/product/technical/
    execution/defensibility). All 5 must now get a query."""
    repo = _FakeEvidenceRepository()
    plan = _plan(
        missing_evidence=["market", "product", "technical", "execution", "defensibility"],
        search_questions=[
            "What is the total addressable market?",
            "What is the product's value proposition?",
            "How complex is the technology?",
            "What is the growth velocity?",
            "How defensible is this business?",
        ],
    )

    with patch("evidence.retrieval.retrieve_source_pack_merged", return_value={"provider": "exa", "sources": []}) as mock_retrieve:
        await execute_evidence_plan(
            user_id="user_test", company_id="company-1", opportunity_id="opp-1",
            plan=plan, evidence_repository=repo, company_name="Acme",
        )

    assert mock_retrieve.call_count == 5


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
    assert items[0].source_quality == 1.0


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
        # Above min_source_quality (0.4) so the claim can be eligible, but
        # below full_confidence_at (0.8) so it's capped, not full-strength.
        assert items[0].source_quality == 0.6


@pytest.mark.asyncio
async def test_sources_from_different_queries_do_not_cross_corroborate():
    """Regression (audit HIGH-B4): corroboration used to be computed once
    across every source from every query pooled together, so a techcrunch.com
    source answering one question and a reuters.com source answering a
    completely different question could "corroborate" each other even though
    neither actually confirms the other's fact. Each query is now scored on
    its own results only -- a single source per query never reaches the >=2
    distinct domains threshold, so both stay unverified."""
    repo = _FakeEvidenceRepository()
    plan = _plan(
        missing_evidence=["market", "execution"],
        search_questions=["market question", "execution question"],
    )

    def side_effect(*, queries, **kwargs):
        if "market" in queries[0]:
            return {
                "provider": "exa",
                "sources": [{"title": "A", "url": "https://techcrunch.com/acme", "snippet": "Market fact."}],
            }
        return {
            "provider": "exa",
            "sources": [{"title": "B", "url": "https://reuters.com/acme", "snippet": "Unrelated execution fact."}],
        }

    with patch("evidence.retrieval.retrieve_source_pack_merged", side_effect=side_effect):
        await execute_evidence_plan(
            user_id="user_test", company_id="company-1", opportunity_id="opp-1",
            plan=plan, evidence_repository=repo, company_name="Acme",
            company_website="https://acme.com",
        )

    assert len(repo.ingested) == 2
    for artifact, items in repo.ingested:
        assert items[0].verification_state == VerificationState.UNVERIFIED
        assert items[0].source_quality == 0.0


@pytest.mark.asyncio
async def test_max_artifacts_budget_is_respected_across_queries():
    """Regression (B4 self-audit): the per-query rewrite ran one retrieval
    call per query, each capped at _MAX_SOURCES_PER_QUERY -- but nothing
    summed those calls against the plan's own max_artifacts budget, so a
    caller-configured budget (routers/evidence.py, jobs/handlers.py) could be
    silently exceeded. A plan with a budget of 2 across 4 queries, each
    returning a distinct never-before-seen source, must still ingest only 2."""
    repo = _FakeEvidenceRepository()
    plan = _plan(
        missing_evidence=["market", "product", "technical", "execution"],
        search_questions=["q1", "q2", "q3", "q4"],
        max_artifacts=2,
    )

    counter = count()

    def side_effect(*, queries, **kwargs):
        n = next(counter)
        return {
            "provider": "exa",
            "sources": [{"title": f"S{n}", "url": f"https://example{n}.com/a", "snippet": f"Fact {n}."}],
        }

    with patch("evidence.retrieval.retrieve_source_pack_merged", side_effect=side_effect):
        result = await execute_evidence_plan(
            user_id="user_test", company_id="company-1", opportunity_id="opp-1",
            plan=plan, evidence_repository=repo, company_name="Acme",
        )

    assert result["artifacts_ingested"] == 2
    assert len(repo.ingested) == 2


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
async def test_verified_source_quality_clears_the_eligibility_floor():
    """EvidenceItemInput.source_quality defaults to 0.0, and this function
    never set it -- every retrieved item was silently below the policy's
    min_source_quality (0.4), making claims linked to it permanently
    ineligible for scoring regardless of verification_state."""
    repo = _FakeEvidenceRepository()
    plan = _plan()
    pack = {
        "provider": "exa",
        "sources": [
            {"title": "Acme homepage", "url": "https://acme.com/about", "snippet": "Acme builds widgets."},
        ],
    }

    with patch("evidence.retrieval.retrieve_source_pack_merged", return_value=pack):
        await execute_evidence_plan(
            user_id="user_test", company_id="company-1", opportunity_id="opp-1",
            plan=plan, evidence_repository=repo, company_name="Acme",
            company_website="https://acme.com",
        )

    _, items = repo.ingested[0]
    assert items[0].source_quality > 0.4


@pytest.mark.asyncio
async def test_verified_items_returned_for_extraction_unverified_excluded():
    """Only verified items are worth handing to Phase C's extraction --
    unverified evidence can never support a scored claim anyway."""
    repo = _FakeEvidenceRepository()
    plan = _plan()
    pack = {
        "provider": "exa",
        "sources": [
            {"title": "Official", "url": "https://acme.com/about", "snippet": "Acme builds widgets."},
            {"title": "Lone blog", "url": "https://randomblog.com/x", "snippet": "Some opinion piece."},
        ],
    }

    with patch("evidence.retrieval.retrieve_source_pack_merged", return_value=pack):
        result = await execute_evidence_plan(
            user_id="user_test", company_id="company-1", opportunity_id="opp-1",
            plan=plan, evidence_repository=repo, company_name="Acme",
            company_website="https://acme.com",
        )

    # Official is verified unconditionally; the lone blog has no corroboration
    # (only 1 non-official domain) so it stays unverified and is excluded.
    assert len(result["verified_items"]) == 1
    assert result["verified_items"][0]["display_excerpt"] == "Acme builds widgets."
    assert "evidence_item_id" in result["verified_items"][0]


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
    assert result == {"artifacts_ingested": 0, "queries_run": 0, "verified_items": []}
