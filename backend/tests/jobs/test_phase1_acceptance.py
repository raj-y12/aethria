import asyncio
import json
import os
import subprocess
import sys
from pathlib import Path
from uuid import uuid4

import pytest

from jobs.models import AgentJob, JobStatus, JobType, PipelineCyclePayload


BACKEND = Path(__file__).resolve().parents[2]


def test_phase1_readiness_cli_reports_missing_direct_database_without_exposing_secrets():
    env = dict(os.environ)
    env.pop("DATABASE_URL", None)
    env.pop("SUPABASE_DB_URL", None)
    env.pop("TEST_DATABASE_URL", None)

    completed = subprocess.run(
        [sys.executable, "scripts/check_phase1_readiness.py", "--json"],
        cwd=BACKEND,
        env=env,
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 1
    result = json.loads(completed.stdout)
    assert result["ready"] is False
    checks = {item["name"]: item for item in result["checks"]}
    assert checks["direct_database_dsn"]["status"] == "blocked"
    assert checks["golden_set_v1"]["status"] == "passed"
    assert checks["meta_analysis_only"]["status"] == "passed"
    assert "postgres://" not in completed.stdout + completed.stderr


@pytest.mark.asyncio
async def test_durable_job_survives_repository_recreation_and_recovers_expired_lease():
    dsn = os.getenv("TEST_DATABASE_URL")
    if not dsn:
        pytest.skip("TEST_DATABASE_URL is required for target-PostgreSQL acceptance")

    import asyncpg

    from jobs.repository import DurableJobRepository

    user_id = f"phase1-acceptance-{uuid4()}"
    job = AgentJob(
        user_id=user_id,
        job_type=JobType.PIPELINE_CYCLE,
        idempotency_key=f"phase1:{uuid4()}",
        payload=PipelineCyclePayload(user_id=user_id, manual_one_shot=True),
        priority=2_000_000_000,
    )

    first_pool = await asyncpg.create_pool(dsn=dsn, min_size=1, max_size=2)
    try:
        first_repository = DurableJobRepository(first_pool)
        accepted = await first_repository.enqueue(job)
        assert accepted.status is JobStatus.QUEUED
    finally:
        await first_pool.close()

    second_pool = await asyncpg.create_pool(dsn=dsn, min_size=1, max_size=3)
    try:
        repository = DurableJobRepository(second_pool)
        claims = await asyncio.gather(
            repository.claim_next(worker_id="phase1-worker-a", lease_seconds=60),
            repository.claim_next(worker_id="phase1-worker-b", lease_seconds=60),
        )
        target_claims = [candidate for candidate in claims if candidate and candidate.job_id == job.job_id]
        assert len(target_claims) == 1
        first_claim = target_claims[0]

        await repository.write_checkpoint(
            user_id=user_id,
            job_id=job.job_id,
            pipeline_run_id=job.pipeline_run_id,
            stage="accepted",
            attempt=first_claim.attempts,
            status="succeeded",
            output_metadata={"job_id": job.job_id},
        )
        async with second_pool.acquire() as conn:
            await conn.execute(
                "update public.agent_jobs set lease_expires_at = now() - interval '1 second' where job_id = $1",
                job.job_id,
            )

        recovered = await repository.claim_next(
            worker_id="phase1-worker-recovery", lease_seconds=60
        )
        assert recovered is not None and recovered.job_id == job.job_id
        assert recovered.attempts == first_claim.attempts + 1
        assert await repository.succeed(
            user_id=user_id,
            job_id=job.job_id,
            worker_id=first_claim.lease_owner,
        ) is False
        assert await repository.succeed(
            user_id=user_id,
            job_id=job.job_id,
            worker_id="phase1-worker-recovery",
        ) is True

        duplicate = await repository.enqueue(job)
        assert duplicate.job_id == job.job_id
        assert duplicate.status is JobStatus.SUCCEEDED
        assert await repository.get_job(user_id=f"other-{uuid4()}", job_id=job.job_id) is None

        async with second_pool.acquire() as conn:
            event_types = await conn.fetch(
                "select event_type from public.domain_outbox where aggregate_id = $1",
                job.job_id,
            )
        assert [row["event_type"] for row in event_types].count("agent_job.accepted") == 1
        assert [row["event_type"] for row in event_types].count("agent_job.succeeded") == 1
    finally:
        async with second_pool.acquire() as conn:
            await conn.execute(
                "delete from public.domain_outbox where aggregate_id = $1", job.job_id
            )
            await conn.execute("delete from public.agent_jobs where job_id = $1", job.job_id)
        await second_pool.close()
