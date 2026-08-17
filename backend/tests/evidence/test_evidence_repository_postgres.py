import os
from uuid import uuid4

import pytest


pytestmark = pytest.mark.skipif(
    not os.getenv("TEST_DATABASE_URL"),
    reason="TEST_DATABASE_URL is required for evidence repository contract tests",
)


async def _admit_company(pool, user_id: str):
    from identity.models import SourceChannel, SourceObservationInput
    from identity.repository import IdentityRepository
    from identity.service import IdentityService

    service = IdentityService(IdentityRepository(pool))
    admission = await service.admit(
        SourceObservationInput(
            user_id=user_id,
            channel=SourceChannel.MANUAL_LOOKUP,
            observed_name="Evidence Dedup Co",
            observed_domain=f"dedup-{uuid4()}.example",
            external_event_key=f"evidence-dedup:{uuid4()}",
            source_metadata={"operator_confirmed_identity": True},
            resolution_payload={"confidence": 1, "resolution_status": "FOUND"},
        )
    )
    return admission.company_id, admission.opportunity_id


async def _cleanup(pool, user_id: str):
    async with pool.acquire() as conn:
        await conn.execute("delete from public.evidence_items where user_id = $1", user_id)
        await conn.execute("delete from public.evidence_artifacts where user_id = $1", user_id)
        await conn.execute("delete from public.domain_outbox where user_id = $1", user_id)
        await conn.execute("delete from public.identity_resolution_cases where user_id = $1", user_id)
        await conn.execute("delete from public.company_aliases where user_id = $1", user_id)
        await conn.execute("delete from public.company_identifiers where user_id = $1", user_id)
        await conn.execute(
            "update public.source_observations set opportunity_id = null where user_id = $1", user_id
        )
        await conn.execute("delete from public.opportunities where user_id = $1", user_id)
        await conn.execute("delete from public.source_observations where user_id = $1", user_id)
        await conn.execute("delete from public.companies where user_id = $1", user_id)


@pytest.mark.asyncio
async def test_reingesting_the_same_artifact_and_item_does_not_duplicate_evidence_items():
    # Audit HIGH-B5: evidence_items had no content-based dedup, so running the
    # same evidence plan twice (a real, checked scenario -- the backfill
    # script overlapping a live dispatch) created duplicate current claims,
    # since evaluate_snapshot averages every current claim of a type.
    import asyncpg

    from evidence.models import (
        AccessClass,
        ArtifactType,
        EvidenceArtifactInput,
        EvidenceItemInput,
        TrustClass,
        VerificationState,
    )
    from evidence.repository import EvidenceRepository

    pool = await asyncpg.create_pool(os.environ["TEST_DATABASE_URL"], min_size=1, max_size=4)
    user_id = f"evidence-dedup-{uuid4()}"
    content = "The company reported 40% month-over-month growth in Q2."

    try:
        company_id, opportunity_id = await _admit_company(pool, user_id)
        repository = EvidenceRepository(pool)

        artifact_input = EvidenceArtifactInput(
            user_id=user_id,
            company_id=company_id,
            opportunity_id=opportunity_id,
            artifact_type=ArtifactType.WEB_PAGE,
            source_uri="https://example.com/growth",
            title="Growth update",
            content_hash="dedup-test-hash-abc123",
            trust_class=TrustClass.INDEPENDENT,
            access_class=AccessClass.PUBLIC,
            retrieval_provider="test-provider",
            retrieval_query="growth rate",
        )

        def make_item() -> EvidenceItemInput:
            return EvidenceItemInput(
                user_id=user_id,
                item_type="retrieval_excerpt",
                display_excerpt=content,
                source_locator="https://example.com/growth",
                verification_state=VerificationState.VERIFIED,
                source_quality=0.6,
            )

        artifact_1, items_1 = await repository.ingest_artifact(artifact_input, items=[make_item()])
        artifact_2, items_2 = await repository.ingest_artifact(artifact_input, items=[make_item()])

        assert artifact_1.artifact_id == artifact_2.artifact_id
        assert len(items_1) == 1
        assert len(items_2) == 1
        assert items_1[0].evidence_item_id == items_2[0].evidence_item_id

        async with pool.acquire() as conn:
            count = await conn.fetchval(
                "select count(*) from public.evidence_items where user_id = $1 and artifact_id = $2",
                user_id, artifact_1.artifact_id,
            )
        assert count == 1
    finally:
        await _cleanup(pool, user_id)
        await pool.close()


@pytest.mark.asyncio
async def test_reingesting_the_same_artifact_with_different_item_content_creates_a_second_item():
    import asyncpg

    from evidence.models import (
        AccessClass,
        ArtifactType,
        EvidenceArtifactInput,
        EvidenceItemInput,
        TrustClass,
        VerificationState,
    )
    from evidence.repository import EvidenceRepository

    pool = await asyncpg.create_pool(os.environ["TEST_DATABASE_URL"], min_size=1, max_size=4)
    user_id = f"evidence-dedup-{uuid4()}"

    try:
        company_id, opportunity_id = await _admit_company(pool, user_id)
        repository = EvidenceRepository(pool)

        artifact_input = EvidenceArtifactInput(
            user_id=user_id,
            company_id=company_id,
            opportunity_id=opportunity_id,
            artifact_type=ArtifactType.WEB_PAGE,
            source_uri="https://example.com/growth",
            title="Growth update",
            content_hash="dedup-test-hash-def456",
            trust_class=TrustClass.INDEPENDENT,
            access_class=AccessClass.PUBLIC,
        )

        _artifact_1, items_1 = await repository.ingest_artifact(
            artifact_input,
            items=[
                EvidenceItemInput(
                    user_id=user_id,
                    item_type="retrieval_excerpt",
                    display_excerpt="First distinct excerpt about growth.",
                    verification_state=VerificationState.VERIFIED,
                )
            ],
        )
        _artifact_2, items_2 = await repository.ingest_artifact(
            artifact_input,
            items=[
                EvidenceItemInput(
                    user_id=user_id,
                    item_type="retrieval_excerpt",
                    display_excerpt="Second, entirely different excerpt.",
                    verification_state=VerificationState.VERIFIED,
                )
            ],
        )

        assert items_1[0].evidence_item_id != items_2[0].evidence_item_id
    finally:
        await _cleanup(pool, user_id)
        await pool.close()
